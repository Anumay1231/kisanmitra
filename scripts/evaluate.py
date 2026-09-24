"""Run the agent on the test scenarios and score tool selection, arithmetic and error handling."""
import ast
import json
import os
import re
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from kisanmitra import config  # noqa: E402
from kisanmitra.agent import build_conversational_agent, get_llm, run  # noqa: E402


def run_with_backoff(chain, llm, question, session_id, attempts: int = 4):
    """Free Groq keys have a low tokens-per-minute limit. On a 429, wait and try again."""
    for attempt in range(attempts):
        try:
            return run(chain, llm, question, session_id=session_id, verbose=True)
        except Exception as exc:
            text = str(exc)
            if "rate_limit" not in text and "429" not in text:
                raise
            wait = 30 * (attempt + 1)
            m = re.search(r"try again in ([\d.]+)s", text)
            if m:
                wait = max(float(m.group(1)) + 5, 20)
            print(f"  rate limited, waiting {wait:.0f}s (attempt {attempt + 1}/{attempts})")
            time.sleep(wait)
    raise RuntimeError("Still rate limited after several retries; wait a minute and re-run.")


def emi(principal, annual_rate_percent, years):
    r = annual_rate_percent / 12 / 100
    n = years * 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def verify_calculations(tool_log: str) -> str:
    """Independently re-compute every EMI the calculator tool returned, using the arguments the
    agent actually passed. This checks the tool's arithmetic without assuming which machine it chose."""
    checks, bad = 0, []
    for line in tool_log.splitlines():
        if not line.startswith("calculate_purchase_plan("):
            continue
        args_text = line[len("calculate_purchase_plan("):line.rindex(") ->")]
        try:
            args = ast.literal_eval(args_text)
            quoted = int(re.search(r"emi=Rs ([\d,]+)", line).group(1).replace(",", ""))
        except (ValueError, SyntaxError, AttributeError):
            continue
        principal = (args["price_inr"] * (1 - args.get("subsidy_percent", 0) / 100)
                     - args.get("down_payment_inr", 0))
        expected = round(emi(principal, args.get("annual_rate_percent", 9.5), args.get("years", 5)))
        checks += 1
        if abs(expected - quoted) > 2:
            bad.append(f"{quoted} vs expected {expected}")
    if not checks:
        return ""
    return f"verified ({checks} calculation(s))" if not bad else "mismatch: " + "; ".join(bad)


def evaluate(chain, llm, scenarios, pause: float = config.EVAL_PAUSE) -> pd.DataFrame:
    rows = []
    for s in scenarios:
        t0 = time.time()
        print(f"\n[{s['id']}] {s['category']}")
        out = run_with_backoff(chain, llm, s["question"], s.get("session", s["id"]))
        latency = round(time.time() - t0, 2)
        steps = out["result"].get("intermediate_steps", [])
        called = [a.tool for a, _ in steps]
        observations = " ".join(str(o) for _, o in steps)
        expected = s.get("expected_tools", [])
        rows.append({
            "id": s["id"], "category": s["category"], "question": s["question"],
            "tools_called": ", ".join(called) or "(none)",
            "expected_tools": ", ".join(expected) or "(none)",
            "tool_selection_ok": set(expected).issubset(set(called)) if expected else called == [],
            "steps": len(steps),
            "tool_error_seen": "TOOL_ERROR" in observations,
            "error_handled_ok": (("TOOL_ERROR" in observations) == s.get("expect_tool_error", False)),
            "answer": out["result"]["output"],
            "key_figures": "; ".join(out["card"].key_figures),
            "confidence": out["card"].confidence,
            "data_gaps": out["card"].data_gaps,
            "latency_s": latency,
            "tool_log": out["tool_log"],
        })
        print("-" * 95)
        time.sleep(pause)   # stay under the free-tier tokens-per-minute limit
    df = pd.DataFrame(rows)
    df["arithmetic_check"] = df["tool_log"].apply(verify_calculations)
    return df


def summarise(df: pd.DataFrame):
    print(f"Tool selection correct : {df['tool_selection_ok'].mean():.0%} ({df['tool_selection_ok'].sum()}/{len(df)})")
    print(f"Error handling correct : {df['error_handled_ok'].mean():.0%}")
    print(f"Mean tool calls        : {df['steps'].mean():.1f}")
    print(f"Mean latency           : {df['latency_s'].mean():.1f}s")
    arith = [a for a in df["arithmetic_check"] if a]
    if arith:
        ok = sum(a.startswith("verified") for a in arith)
        print(f"Independent EMI check  : {ok}/{len(arith)} scenarios verified" +
              ("" if ok == len(arith) else " -> " + "; ".join(a for a in arith if not a.startswith('verified'))))


if __name__ == "__main__":
    scenarios = json.load(open(os.path.join(os.path.dirname(__file__), "..", "eval", "test_scenarios.json")))
    llm = get_llm()
    extra = []
    try:                                    # scheme retriever tool, if the PDFs and model are available
        from kisanmitra.knowledge import build_scheme_retriever, download_scheme_pdfs, make_scheme_tool
        retriever = build_scheme_retriever(download_scheme_pdfs())
        if retriever:
            extra = [make_scheme_tool(retriever)]
    except Exception as exc:
        print(f"Scheme tool unavailable: {exc}")
    chain, _, _ = build_conversational_agent(llm, extra_tools=extra)
    df = evaluate(chain, llm, scenarios)
    os.makedirs("eval", exist_ok=True)
    df.to_csv("eval/results.csv", index=False)
    summarise(df)
