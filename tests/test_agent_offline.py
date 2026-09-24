import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from fake_llm import ScriptedToolLLM
from kisanmitra.agent import build_conversational_agent, run

def test_multi_tool_flow():
    llm = ScriptedToolLLM(script=[
        ("search_inventory", {"category": "tractor", "max_price": 900000}),
        ("calculate_purchase_plan", {"price_inr": 850000, "subsidy_percent": 40, "down_payment_inr": 100000}),
        "The JD 5050D at Rs 8,50,000 fits: after 40% subsidy and Rs 1,00,000 down payment the EMI is Rs 8,611/month.",
    ])
    chain, store, tools = build_conversational_agent(llm, verbose=False)
    out = run(chain, llm, "Which tractor under 9 lakh suits me and what would the EMI be?", "t1", verbose=False)
    steps = out["result"]["intermediate_steps"]
    assert [s[0].tool for s in steps] == ["search_inventory", "calculate_purchase_plan"], steps
    assert "8,611" in out["result"]["output"]
    assert out["card"].confidence == "high"
    assert len(store["t1"].messages) == 2
    print("PASS multi-tool flow:", [s[0].tool for s in steps])

def test_tool_error_handling():
    llm = ScriptedToolLLM(script=[
        ("get_weather_forecast", {"location": "Nowhereville", "days": 3}),
        "I could not fetch the forecast, so I cannot advise on spraying today.",
    ])
    chain, _, _ = build_conversational_agent(llm, verbose=False)
    out = run(chain, llm, "Can I spray tomorrow in Nowhereville?", "t2", verbose=False)
    obs = out["result"]["intermediate_steps"][0][1]
    assert "TOOL_ERROR" in obs, obs
    assert "could not fetch" in out["result"]["output"]
    print("PASS tool-error handling:", obs[:60])

def test_no_tool_needed():
    llm = ScriptedToolLLM(script=["I can help with machines, service, subsidies and field timing."])
    chain, _, _ = build_conversational_agent(llm, verbose=False)
    out = run(chain, llm, "What can you do?", "t3", verbose=False)
    assert out["result"]["intermediate_steps"] == []
    print("PASS no-tool path")

def test_max_iterations_guard():
    llm = ScriptedToolLLM(script=[("check_part_stock", {"query": "filter"})] * 20)
    chain, _, _ = build_conversational_agent(llm, verbose=False, max_iterations=3)
    out = run(chain, llm, "loop test", "t4", verbose=False)
    assert len(out["result"]["intermediate_steps"]) <= 3
    print("PASS max-iteration guard:", len(out["result"]["intermediate_steps"]), "steps")

if __name__ == "__main__":
    test_multi_tool_flow(); test_tool_error_handling(); test_no_tool_needed(); test_max_iterations_guard()
    print("\nAll offline agent tests passed.")
