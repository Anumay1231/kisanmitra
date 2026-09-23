"""Gradio chat UI for KisanMitra: python app.py"""
import os
import sys
import uuid

import gradio as gr

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from kisanmitra.agent import build_conversational_agent, get_llm, run  # noqa: E402

llm = get_llm()
extra = []
try:
    from kisanmitra.knowledge import build_scheme_retriever, download_scheme_pdfs, make_scheme_tool
    retriever = build_scheme_retriever(download_scheme_pdfs())
    if retriever:
        extra = [make_scheme_tool(retriever)]
except Exception as exc:
    print(f"Scheme tool unavailable: {exc}")

chain, _, tools = build_conversational_agent(llm, extra_tools=extra, verbose=False)
SESSION = str(uuid.uuid4())


def respond(message, history):
    out = run(chain, llm, message, session_id=SESSION, verbose=False)
    card = out["card"]
    text = out["result"]["output"]
    if card.key_figures:
        text += "\n\n**Key figures:** " + "; ".join(card.key_figures)
    text += f"\n\n**Tools used:** {', '.join(card.tools_used) or 'none'} · **Confidence:** {card.confidence}"
    if card.data_gaps:
        text += f"\n\n⚠️ {card.data_gaps}"
    return text


demo = gr.ChatInterface(
    respond,
    title="KisanMitra 🚜 — dealership operations agent",
    description=f"Tools available: {', '.join(t.name for t in tools)}",
    examples=["Which tractors under 9 lakh are in stock?",
              "EMI for the JD 5050D with 40% subsidy, 1 lakh down payment, 5 years?",
              "Is the weather near Dhamtari good for spraying in the next 3 days?"],
)

if __name__ == "__main__":
    demo.launch(share=True)
