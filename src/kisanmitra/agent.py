"""Agent assembly: tool-calling agent + executor + conversational memory + structured summary chain."""
from __future__ import annotations

import os

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory

from . import config
from .prompts import AGENT_PROMPT, SUMMARY_PROMPT
from .schema import AdviceCard
from .tools import BASE_TOOLS

card_parser = PydanticOutputParser(pydantic_object=AdviceCard)


# Groq lists models a key may not actually be allowed to call, so we probe candidates with a
# one-token request and keep the first that answers. Tool calling needs a capable chat model.
PREFERRED_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]
SKIP = ("whisper", "tts", "guard", "embed", "vision", "distil", "prompt-guard")


def list_available_models() -> list[str]:
    """Model ids the API lists for this key (not all of them are necessarily callable)."""
    from groq import Groq
    return sorted(m.id for m in Groq().models.list().data)


def model_works(name: str) -> bool:
    """Cheapest possible check that this key can actually call the model."""
    from langchain_groq import ChatGroq
    try:
        ChatGroq(model=name, temperature=0, max_tokens=1).invoke("hi")
        return True
    except Exception as exc:
        print(f"  {name}: unavailable ({str(exc)[:80]})")
        return False


def pick_model(verbose: bool = True) -> str:
    """Return the best model this key can really use. Set KM_LLM_MODEL to override."""
    if os.getenv("KM_LLM_MODEL"):
        return os.environ["KM_LLM_MODEL"]
    try:
        available = list_available_models()
    except Exception as exc:
        print(f"Could not list models ({exc}); trying the preferred list directly")
        available = list(PREFERRED_MODELS)
    candidates = [m for m in PREFERRED_MODELS if m in available]
    candidates += [m for m in available
                   if m not in candidates and not any(s in m.lower() for s in SKIP)]
    if verbose:
        print("Testing which models this key can call:")
    for name in candidates:
        if model_works(name):
            if verbose:
                print(f"Using model: {name}")
            os.environ["KM_LLM_MODEL"] = name      # remember for the rest of the session
            return name
    raise RuntimeError(f"None of these models could be called with this key: {candidates}")


def get_llm(model: str | None = None, temperature: float = config.TEMPERATURE,
            max_tokens: int = config.MAX_TOKENS, max_retries: int = config.MAX_RETRIES):
    """Chat model for the agent. Tool calling is required, so the model must support it.

    max_retries lets the Groq client wait out free-tier rate limits (HTTP 429) instead of failing,
    and max_tokens caps answer length so one question uses fewer tokens per minute.
    """
    from langchain_groq import ChatGroq
    return ChatGroq(model=model or pick_model(), temperature=temperature,
                    max_tokens=max_tokens, max_retries=max_retries)


def build_agent(llm, extra_tools=(), max_iterations: int = config.MAX_ITERATIONS, verbose: bool = True):
    """Return (executor, tools). The executor runs the think -> call tool -> observe loop."""
    tools = list(BASE_TOOLS) + list(extra_tools)
    agent = create_tool_calling_agent(llm, tools, AGENT_PROMPT)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        max_iterations=max_iterations,
        return_intermediate_steps=True,      # needed for evaluation and for the demo
        handle_parsing_errors="Reply with a normal answer or a valid tool call.",
    )
    return executor, tools


def build_conversational_agent(llm, **kwargs):
    executor, tools = build_agent(llm, **kwargs)
    store: dict[str, InMemoryChatMessageHistory] = {}

    def get_history(session_id: str):
        return store.setdefault(session_id, InMemoryChatMessageHistory())

    chain = RunnableWithMessageHistory(
        executor, get_history, input_messages_key="input", history_messages_key="history",
        output_messages_key="output",
    )
    return chain, store, tools


def tool_log(result) -> str:
    """Readable log of every tool call the agent made: name, arguments, observation."""
    lines = []
    for action, observation in result.get("intermediate_steps", []):
        obs = str(observation).replace("\n", " | ")
        lines.append(f"{action.tool}({action.tool_input}) -> {obs[:400]}")
    return "\n".join(lines) if lines else "(no tools were called)"


def summarise(llm, question: str, result) -> AdviceCard:
    """LCEL chain that turns the agent's free-text answer into a validated AdviceCard."""
    chain = SUMMARY_PROMPT.partial(format_instructions=card_parser.get_format_instructions()) | llm | StrOutputParser()
    raw = chain.invoke({"input": question, "output": result["output"], "tool_log": tool_log(result)})
    try:
        return card_parser.parse(raw)
    except OutputParserException:
        fixed = llm.invoke("Return ONLY valid JSON for this schema.\n"
                           f"{card_parser.get_format_instructions()}\n\nText:\n{raw}")
        try:
            return card_parser.parse(fixed.content)
        except OutputParserException:
            return AdviceCard(recommendation=result["output"][:400], key_figures=[], tools_used=[],
                              data_gaps="structured summary unavailable", confidence="low")


STOPPED = "Agent stopped due to max iterations"


def run(chain, llm, question: str, session_id: str = "default", verbose: bool = True):
    result = chain.invoke({"input": question}, config={"configurable": {"session_id": session_id}})
    if STOPPED in result["output"]:
        # The agent used up its tool budget (usually by re-asking one tool). Salvage an answer from
        # the observations it already collected instead of returning the framework's stop message.
        salvage = llm.invoke(
            "Answer the user's question using ONLY the tool results below. Quote figures exactly and "
            "say plainly what could not be confirmed.\n\n"
            f"Question: {question}\n\nTool results:\n{tool_log(result)}"
        )
        result["output"] = salvage.content.strip() + "\n\n(Answer assembled after the tool-call limit was reached.)"
    card = summarise(llm, question, result)
    if verbose:
        print(f"\nQ: {question}\nA: {result['output']}")
        print("Tools called:\n  " + tool_log(result).replace("\n", "\n  "))
        print(f"Card: {card.model_dump()}")
    return {"result": result, "card": card, "tool_log": tool_log(result)}
