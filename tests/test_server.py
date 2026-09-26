"""Tests for the web API (server.py). No API key needed: python tests/test_server.py

1. Agent mode with the scripted LLM: tool calls stream as tool_start / tool_end events, then a final answer.
2. Demo mode: the rule-based router calls the real tools and returns a card.
3. /api/health and /api/inventory return what the frontend expects.
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
os.environ.pop("GROQ_API_KEY", None)          # start in demo mode; agent mode is switched on below

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from fake_llm import ScriptedToolLLM  # noqa: E402
from kisanmitra.agent import build_conversational_agent  # noqa: E402

client = TestClient(server.app)


def events(message, session="t"):
    with client.stream("POST", "/api/chat", json={"message": message, "session_id": session}) as r:
        assert r.status_code == 200, r.status_code
        return [json.loads(line) for line in r.iter_lines() if line]


def test_health_and_inventory():
    h = client.get("/api/health").json()
    assert h["mode"] == "demo"
    names = {t["name"] for t in h["tools"]}
    assert {"search_inventory", "calculate_purchase_plan", "lookup_scheme_rules"} <= names
    inv = client.get("/api/inventory").json()
    assert inv["machines"] and inv["parts"]
    print("PASS health + inventory")


def test_demo_mode():
    ev = events("Suggest a tractor under 9 lakh with 1 lakh down payment and 40% subsidy. EMI over 5 years?", "d1")
    tools = [e["tool"] for e in ev if e["type"] == "tool_start"]
    assert tools == ["search_inventory", "calculate_purchase_plan"], tools
    final = ev[-1]
    assert final["type"] == "final" and "EMI" in final["answer"], final
    follow = events("What if I take it for 7 years instead?", "d1")[-1]
    assert "7 years" in follow["answer"], follow["answer"]
    print("PASS demo mode (multi-step + memory follow-up)")


def test_agent_mode_streams_tool_calls():
    llm = ScriptedToolLLM(script=[
        ("search_inventory", {"category": "tractor", "max_price": 900000}),
        ("calculate_purchase_plan", {"price_inr": 850000, "subsidy_percent": 40,
                                     "down_payment_inr": 100000, "years": 5}),
        "The JD 5050D fits. EMI is Rs 8,611/month.",
    ])
    chain, _, tools = build_conversational_agent(llm, verbose=False)
    server.STATE.update(llm=llm, chain=chain, tools=tools, model="scripted")
    server.DEMO = False
    try:
        ev = events("EMI for a tractor under 9 lakh?", "a1")
    finally:
        server.DEMO = True
    kinds = [e["type"] for e in ev]
    starts = [e for e in ev if e["type"] == "tool_start"]
    ends = [e for e in ev if e["type"] == "tool_end"]
    assert [s["tool"] for s in starts] == ["search_inventory", "calculate_purchase_plan"], starts
    assert len(ends) == 2 and all(not e["error"] for e in ends)
    assert {s["id"] for s in starts} == {e["id"] for e in ends}, "tool_end ids must match tool_start ids"
    assert kinds.index("tool_start") < kinds.index("tool_end") < kinds.index("final")
    final = ev[-1]
    assert final["type"] == "final" and final["card"]["confidence"] in ("high", "medium", "low")
    assert "emi=Rs" in ends[1]["output"]
    print("PASS agent mode streams tool calls:", [s["tool"] for s in starts])


if __name__ == "__main__":
    test_health_and_inventory()
    test_demo_mode()
    test_agent_mode_streams_tool_calls()
    print("\nAll server tests passed.")
