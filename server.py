"""FastAPI backend for the KisanMitra web frontend: python server.py

Endpoints
  GET  /api/health        mode, model and the tools the agent can call
  GET  /api/inventory     machines and spare parts from the dealership database
  POST /api/chat          {message, session_id} -> streamed NDJSON events:
                            {"type": "thinking"}                       the model is deciding the next step
                            {"type": "tool_start", "id", "tool", "input"}
                            {"type": "tool_end",   "id", "output", "error"}
                            {"type": "final", "answer", "card", "latency_ms"}
                            {"type": "error", "message"}

Mode
  With GROQ_API_KEY set, the real LangChain agent answers.
  Without it (or with KM_DEMO=1), a rule-based demo router calls the SAME tools so the UI can be
  tried without a key. The UI shows which mode is active.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import re
import sqlite3
import sys
import threading
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

def _load_env_file(path: str) -> None:
    """Read KEY=value lines from .env (no extra package needed). Real environment variables win."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(os.path.join(ROOT, ".env"))
for _k in ("GROQ_API_KEY", "DATAGOV_API_KEY"):          # ignore the placeholders from .env.example
    if os.getenv(_k, "").strip() in ("", "your_key_here", "optional_data_gov_in_key"):
        os.environ.pop(_k, None)

from kisanmitra import config  # noqa: E402
from kisanmitra.tools import BASE_TOOLS  # noqa: E402

TOOLS_BY_NAME = {t.name: t for t in BASE_TOOLS}
DEMO = os.getenv("KM_DEMO") == "1" or not os.getenv("GROQ_API_KEY")

STATE: dict[str, Any] = {"llm": None, "chain": None, "tools": list(BASE_TOOLS), "model": None,
                         "scheme_tool": False, "warning": None}


def _init_agent() -> None:
    """Build the real agent once. Falls back to demo mode if anything fails."""
    global DEMO
    if DEMO:
        return
    try:
        from kisanmitra.agent import build_conversational_agent, get_llm
        llm = get_llm()
        extra = []
        if os.getenv("KM_NO_RAG") != "1":
            try:
                from kisanmitra.knowledge import build_scheme_retriever, download_scheme_pdfs, make_scheme_tool
                retriever = build_scheme_retriever(download_scheme_pdfs())
                if retriever:
                    extra = [make_scheme_tool(retriever)]
                    STATE["scheme_tool"] = True
            except Exception as exc:  # the agent still works without the RAG tool
                print(f"Scheme tool unavailable: {exc}")
        chain, _, tools = build_conversational_agent(llm, extra_tools=extra, verbose=False)
        STATE.update(llm=llm, chain=chain, tools=tools, model=os.getenv("KM_LLM_MODEL", config.LLM_MODEL))
    except Exception as exc:
        print(f"Could not start the LLM agent ({exc}); running in demo mode.")
        STATE["warning"] = f"Could not start the AI model, so this is demo mode. Reason: {exc}"[:300]
        DEMO = True


if not os.path.exists(config.DB_PATH):
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "seed_db.py")], check=True)
_init_agent()

app = FastAPI(title="KisanMitra API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ helpers

def _tool_status(name: str) -> str:
    if name == "get_mandi_price" and not config.DATAGOV_KEY:
        return "needs_key"
    return "ok"


def _first_sentence(text: str) -> str:
    text = " ".join((text or "").split())
    return text.split(". ")[0].rstrip(".") + "."


def _is_error(output: str) -> bool:
    return str(output).startswith("TOOL_ERROR")


# ------------------------------------------------------------------ read-only endpoints

@app.get("/api/health")
def health():
    tools = STATE["tools"]
    names = {t.name for t in tools}
    listed = [{"name": t.name, "description": _first_sentence(t.description), "status": _tool_status(t.name)}
              for t in tools]
    if "lookup_scheme_rules" not in names:
        listed.append({"name": "lookup_scheme_rules",
                       "description": "Search SMAM subsidy guidelines with page citations.",
                       "status": "unavailable"})
    return {"mode": "demo" if DEMO else "agent", "model": None if DEMO else STATE["model"], "tools": listed,
            "warning": STATE["warning"], "public": PUBLIC,
            "rate_limit": RATE_LIMIT if PUBLIC else None}


@app.get("/api/inventory")
def inventory():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        machines = [dict(r) for r in con.execute(
            "SELECT model, category, hp, price_inr, stock, fuel_lph, notes FROM machines ORDER BY category, price_inr")]
        parts = [dict(r) for r in con.execute("SELECT part_no, name, model, price_inr, stock FROM parts")]
    finally:
        con.close()
    return {"machines": machines, "parts": parts}


# ------------------------------------------------------------------ real agent (streams tool calls)

def _run_agent(message: str, session_id: str, emit) -> dict:
    from langchain_core.callbacks import BaseCallbackHandler
    from kisanmitra.agent import run

    class Streamer(BaseCallbackHandler):
        def on_chat_model_start(self, *args, **kwargs):
            emit({"type": "thinking"})

        def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs):
            emit({"type": "tool_start", "id": str(run_id), "tool": (serialized or {}).get("name", "tool"),
                  "input": inputs if inputs is not None else input_str})

        def on_tool_end(self, output, *, run_id, **kwargs):
            text = getattr(output, "content", output)
            emit({"type": "tool_end", "id": str(run_id), "output": str(text), "error": _is_error(str(text))})

        def on_tool_error(self, error, *, run_id, **kwargs):
            emit({"type": "tool_end", "id": str(run_id), "output": f"TOOL_ERROR: {error}", "error": True})

    out = run(STATE["chain"], STATE["llm"], message, session_id=session_id, verbose=False, callbacks=[Streamer()])
    return {"answer": out["result"]["output"], "card": out["card"].model_dump()}


# ------------------------------------------------------------------ demo router (no LLM, real tools)

LOCATIONS = ["Dhamtari", "Raipur", "Durg", "Bilaspur", "Rajnandgaon", "Bemetara", "Mahasamund", "Korba", "Jagdalpur"]
CUSTOMERS = ["Ramesh Sahu", "Devendra Patel", "Sunita Verma", "Gopal Yadav", "Mahesh Chandrakar"]
MODELS = ["JD 5310 4WD", "JD W70 Harvester", "JD 5050D", "JD 5105", "JD 3028EN"]
DEMO_MEMORY: dict[str, dict] = {}


def _date(iso: str) -> str:
    """2026-04-17 -> 17 Apr 2026 (the date style the agent prompt asks for)."""
    try:
        from datetime import date
        return date.fromisoformat(iso).strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return iso


def _inr(x: float) -> str:
    """Indian digit grouping: 850000 -> 8,50,000."""
    n = str(int(round(x)))
    if len(n) <= 3:
        return n
    head, tail = n[:-3], n[-3:]
    head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
    return f"{head},{tail}"


def _money(text: str, *patterns: str) -> float | None:
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            value = float(m.group(1).replace(",", ""))
            unit = (m.group(2) if m.lastindex and m.lastindex >= 2 else "") or ""
            return value * (100000 if unit.lower().startswith(("lakh", "lac", "l")) else 1)
    return None


def _demo(message: str, session_id: str, emit) -> dict:
    text = message.lower()
    memory = DEMO_MEMORY.setdefault(session_id, {})
    used: list[str] = []
    figures: list[str] = []
    gaps = ""

    def call(name: str, args: dict) -> str:
        emit({"type": "thinking"})
        time.sleep(0.5)
        rid = uuid.uuid4().hex
        emit({"type": "tool_start", "id": rid, "tool": name, "input": args})
        out = str(TOOLS_BY_NAME[name].invoke(args))
        time.sleep(0.35)
        emit({"type": "tool_end", "id": rid, "output": out, "error": _is_error(out)})
        used.append(name)
        return out

    def fields(line: str) -> dict:
        return dict(kv.split("=", 1) for kv in line.split("; ") if "=" in kv)

    def grab(pattern: str, out: str) -> str | None:
        m = re.search(pattern, out)
        return m.group(1) if m else None

    model = next((m for m in MODELS if m.lower() in text), None)
    years = _money(text, r"(\d+)\s*(?:years?|yrs?)")
    wants_finance = any(k in text for k in ("emi", "subsidy", "loan", "instal", "finance")) or (
        years and memory.get("price"))

    if wants_finance:
        price = memory.get("price")
        name = memory.get("model")
        if model or not price:
            budget = _money(text, r"under\s*(?:rs\.?\s*)?([\d,.]+)\s*(lakh|lac|l\b)?", r"below\s*([\d,.]+)\s*(lakh|lac)?")
            out = call("search_inventory", {"category": "tractor", "max_price": int(budget) if budget else None,
                                            "in_stock_only": True})
            rows = [r for r in out.splitlines() if r.startswith("model=")]
            if model:
                rows = [r for r in rows if f"model={model};" in r] or rows
            if not rows:
                return {"answer": out, "card": _card(out, [], used, "", "medium")}
            name = grab(r"model=([^;]+)", rows[0])
            price = float(grab(r"price_inr=(\d+)", rows[0]))
        subsidy = _money(text, r"(\d+(?:\.\d+)?)\s*%\s*subsidy", r"subsidy\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*%")
        subsidy = subsidy if subsidy is not None else memory.get("subsidy", 0)
        down = _money(text, r"([\d,.]+)\s*(lakh|lac)?\s*down", r"down\s*payment\s*(?:of\s*)?(?:rs\.?\s*)?([\d,.]+)\s*(lakh|lac)?")
        down = down if down is not None else memory.get("down", 0)
        years = int(years or memory.get("years", 5))
        out = call("calculate_purchase_plan", {"price_inr": price, "subsidy_percent": subsidy,
                                               "down_payment_inr": down, "years": years})
        memory.update(price=price, model=name, subsidy=subsidy, down=down, years=years)
        emi = grab(r"emi=(Rs [\d,]+/month)", out)
        interest = grab(r"total_interest=(Rs [\d,]+)", out)
        figures = [f"{name} price Rs {_inr(price)}", f"EMI {emi}", f"Total interest {interest}"]
        answer = (f"The {name} is in stock at Rs {_inr(price)}. With {subsidy:g}% subsidy and "
                  f"Rs {_inr(down)} down payment, the loan works out to an EMI of {emi} over {years} years "
                  f"({years * 12} months at 9.5%). Total interest paid: {interest}.")
        return {"answer": answer, "card": _card(answer, figures, used, gaps, "high")}

    if any(k in text for k in ("weather", "spray", "rain", "harvest", "forecast")):
        place = next((p for p in LOCATIONS if p.lower() in text), None)
        m = re.search(r"(?:near|in|at)\s+([A-Z][a-zA-Z]+)", message)
        place = place or (m.group(1) if m else "Raipur")
        days = int(_money(text, r"(\d)\s*days?") or 3)
        out = call("get_weather_forecast", {"location": place, "days": days})
        if _is_error(out):
            return {"answer": "I could not get the forecast right now, so I cannot say whether it will stay dry.",
                    "card": _card("", [], used, out.replace("TOOL_ERROR: ", ""), "low")}
        rain = [float(x) for x in re.findall(r"rain ([\d.]+) mm", out)]
        dry = [ln.split(":")[0] for ln in out.splitlines()[1:] if float(re.search(r"rain ([\d.]+)", ln).group(1)) < 1]
        verdict = ("Good window for spraying on " + ", ".join(dry) + " (under 1 mm rain expected).") if dry else \
            "Rain is expected on every day, so hold off spraying."
        figures = [f"Rain total {sum(rain):.1f} mm over {days} days"]
        return {"answer": verdict + "\n\n" + out, "card": _card(verdict, figures, used, "", "high")}

    if "service" in text or "repair" in text:
        cust = next((c for c in CUSTOMERS if c.split()[0].lower() in text or c.lower() in text), None)
        out = call("search_service_records", {"customer": cust, "model": model, "limit": 5})
        costs = [int(x) for x in re.findall(r"cost_inr=(\d+)", out)]
        figures = [f"{len(costs)} jobs, total Rs {_inr(sum(costs))}"] if costs else []
        rows = [fields(r) for r in out.splitlines() if "service_date=" in r]
        lines = [f"- {_date(f['service_date'])}: {f['issue']} on {f['model']} (Rs {_inr(int(f['cost_inr']))})"
                 for f in rows]
        answer = (f"Recent service jobs{' for ' + cust if cust else ''}:\n" + "\n".join(lines)) if lines else out
        return {"answer": answer, "card": _card(answer, figures, used, "", "high")}

    if any(k in text for k in ("part", "filter", "tyre", "tire")):
        q = next((k for k in ("oil filter", "fuel filter", "air filter", "hydraulic filter", "tyre", "filter")
                  if k in text), "filter")
        out = call("check_part_stock", {"query": q})
        rows = [fields(r) for r in out.splitlines() if "part_no=" in r]
        lines = [f"- {f['name']} ({f['part_no']}) for {f['model']}: Rs {_inr(int(f['price_inr']))}, "
                 f"{'out of stock' if f['stock'] == '0' else f['stock'] + ' in stock'}" for f in rows]
        answer = "Matching spare parts:\n" + "\n".join(lines) if lines else out
        return {"answer": answer, "card": _card(answer, [], used, "", "high")}

    if any(k in text for k in ("diesel", "fuel", "operating cost")):
        hours = _money(text, r"(\d+)\s*(?:hours?|hrs?)") or 100
        rate = _money(text, r"rs\.?\s*(\d+(?:\.\d+)?)\s*(?:per|/)\s*l") or 95
        out = call("estimate_operating_cost", {"model": model or "JD 5050D", "hours": hours,
                                               "diesel_price_per_litre": rate})
        cost = grab(r"fuel cost = (Rs [\d,]+)", out)
        return {"answer": out, "card": _card(out, [f"Fuel cost {cost}"] if cost else [], used, "",
                                            "low" if _is_error(out) else "high")}

    if "mandi" in text or ("price" in text and any(c in text for c in ("paddy", "wheat", "soyabean", "maize"))):
        crop = "Paddy(Dhan)(Common)" if "paddy" in text or "dhan" in text else text.split("price of")[-1].split()[0].title()
        out = call("get_mandi_price", {"commodity": crop, "state": "Chhattisgarh"})
        if _is_error(out):
            answer = ("Live mandi prices are unavailable because no data.gov.in key is configured. "
                      "If you tell me your expected selling price, I can work out affordability from it.")
            return {"answer": answer, "card": _card(answer, [], used, out.replace("TOOL_ERROR: ", ""), "low")}
        return {"answer": out, "card": _card(out, [], used, "", "high")}

    if any(k in text for k in ("stock", "tractor", "inventory", "harvester", "implement", "machine", "rotavator")):
        cat = next((c for c in ("tractor", "harvester", "implement") if c in text), None)
        budget = _money(text, r"under\s*(?:rs\.?\s*)?([\d,.]+)\s*(lakh|lac|l\b)?", r"below\s*([\d,.]+)\s*(lakh|lac)?")
        hp = _money(text, r"(\d+)\s*\+?\s*hp")
        out = call("search_inventory", {"category": cat, "max_price": int(budget) if budget else None,
                                        "min_hp": int(hp) if hp else None, "in_stock_only": True})
        rows = [fields(r) for r in out.splitlines() if r.startswith("model=")]
        lines = [f"- {f['model']}: {f['hp']} hp, Rs {_inr(int(f['price_inr']))}, {f['stock']} in stock ({f['notes']})"
                 if f['hp'] != '0' else f"- {f['model']}: Rs {_inr(int(f['price_inr']))}, {f['stock']} in stock ({f['notes']})"
                 for f in rows]
        answer = ("In stock now:\n" + "\n".join(lines)) if lines else out
        return {"answer": answer, "card": _card(answer, [f"{len(lines)} matching machines"], used, "", "high")}

    answer = ("I can help with machines in stock, EMI and subsidy plans, service history, spare parts, "
              "diesel cost and spraying weather. That question is outside what I can check.")
    return {"answer": answer, "card": _card(answer, [], used, "", "high")}


def _card(recommendation: str, figures: list[str], used: list[str], gaps: str, confidence: str) -> dict:
    rec = " ".join(recommendation.split()[:60])
    gaps = gaps.split(". ")[0].rstrip(".")
    gaps = (gaps[:1].upper() + gaps[1:] + ".") if gaps else ""
    return {"recommendation": rec, "key_figures": figures, "tools_used": list(dict.fromkeys(used)),
            "data_gaps": gaps, "confidence": confidence}


# ------------------------------------------------------------------ streaming chat endpoint

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="web", max_length=64)


LOCK = threading.Lock()  # Groq free tier: one agent run at a time

# Public-link mode (launch.py --share sets KM_PUBLIC=1): each visitor gets a limited number of questions
# per hour so strangers cannot use up the owner's Groq allowance. Local use has no limit.
PUBLIC = os.getenv("KM_PUBLIC") == "1"
RATE_LIMIT = int(os.getenv("KM_RATE_LIMIT", 20))         # questions per visitor per window
RATE_WINDOW = int(os.getenv("KM_RATE_WINDOW", 3600))     # seconds
_HITS: dict[str, list[float]] = {}
_HITS_LOCK = threading.Lock()


def _visitor(request: Request) -> str:
    # Behind the Cloudflare tunnel every request comes from localhost; the real visitor is in this header.
    return (request.headers.get("cf-connecting-ip")
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown"))


def _allow(visitor: str) -> tuple[bool, int]:
    """Record one question; return (allowed, minutes until the oldest one expires)."""
    now = time.time()
    with _HITS_LOCK:
        hits = [t for t in _HITS.get(visitor, []) if now - t < RATE_WINDOW]
        if len(hits) >= RATE_LIMIT:
            _HITS[visitor] = hits
            return False, max(1, int((RATE_WINDOW - (now - hits[0])) // 60) + 1)
        hits.append(now)
        _HITS[visitor] = hits
        return True, 0


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    q: queue.Queue = queue.Queue()
    started = time.perf_counter()

    if PUBLIC:
        ok, wait_min = _allow(_visitor(request))
        if not ok:
            msg = (f"This shared demo allows {RATE_LIMIT} questions per hour per visitor. "
                   f"Please try again in about {wait_min} minutes.")
            return StreamingResponse(iter([json.dumps({"type": "error", "message": msg}) + "\n"]),
                                     media_type="application/x-ndjson")

    def worker():
        try:
            with LOCK:
                fn = _demo if DEMO else _run_agent
                result = fn(body.message.strip(), body.session_id, q.put)
            q.put({"type": "final", **result, "latency_ms": int((time.perf_counter() - started) * 1000)})
        except Exception as exc:  # surface a readable error to the UI
            q.put({"type": "error", "message": f"{exc.__class__.__name__}: {exc}"[:400]})
        finally:
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def stream():
        while True:
            event = await asyncio.to_thread(q.get)
            if event is None:
                break
            yield json.dumps(event, default=str) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ serve the built frontend

DIST = os.path.join(ROOT, "frontend", "dist")
if not os.path.isdir(DIST):
    @app.get("/")
    def no_frontend():
        return {"error": "frontend/dist is missing. Run: cd frontend && npm install && npm run build"}
else:
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        file = os.path.join(DIST, path)
        return FileResponse(file if path and os.path.isfile(file) else os.path.join(DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\nKisanMitra is running: open http://localhost:{port}  "
          f"(mode: {'demo, no LLM' if DEMO else 'agent, ' + str(STATE['model'])})\nPress Ctrl+C to stop.\n")
    host = os.getenv("KM_HOST", "127.0.0.1")   # launch.py --phone sets 0.0.0.0 so phones on the same Wi-Fi can connect
    uvicorn.run(app, host=host, port=port, log_level="warning")
