# Phase 2 Progress Notes: KisanMitra (Activity 2)
Team: I054 Anumay Pandey · I023 Yash Garg · I037 Yash Kothari

## Completed
- 8 tools implemented with Pydantic argument schemas and docstrings the LLM uses for selection: weather API, mandi price API, three SQLite database tools, two deterministic calculators, and a FAISS scheme retriever exposed as a tool.
- Synthetic dealership database (9 machines, 5 parts, 40 service records) with a seed script.
- Tool-calling agent (`create_tool_calling_agent` + `AgentExecutor`, max 6 iterations, intermediate steps returned) with per-session memory and a structured `AdviceCard` summary chain.
- Every tool returns `TOOL_ERROR: ...` instead of raising, and the system prompt tells the agent how to recover; verified by offline tests.
- Offline test suite that exercises the agent loop with a scripted tool-calling model, so the loop is testable without an API key: multi-tool flow, tool-error handling, no-tool path and the iteration guard all pass.
- Evaluation harness over 9 scenarios with tool-selection, error-handling and latency metrics plus an independent EMI re-computation.

## Current results (Colab run, 24 Sep 2026, Groq `openai/gpt-oss-120b`)
| Metric | Value |
|---|---|
| Tool selection correct | 100% (9/9) |
| Error handling correct | 100% |
| Mean tool calls per question | 1.1 |
| Mean latency | 5.2 s |
| Independent EMI check | 2/2 calculations verified |

Full per-scenario results: `eval/results.csv`. Executed notebook with outputs: `notebooks/KisanMitra_Agent_run.ipynb`.

## Screenshots
`docs/screenshots/`: setup and offline tests, direct tool calls, the model probe, the multi-step agent trace,
the evaluation table and the handled tool failure.

## Issues found and fixed during the run
- The hard-coded model id was rejected by the API key, so the agent now probes each listed model with a one-token call and uses the first that answers.
- The free tier allows 8,000 tokens per minute; answers are capped, the client retries HTTP 429 and scenarios are paced 20 s apart.
- A strict "state only what tools return" rule made the agent re-query the scheme retriever until it hit the iteration cap. Any tool is now limited to two calls per turn, and an answer is assembled from the observations already collected if the cap is reached.
- Re-running the evaluation on the same agent answered repeat questions from memory without calling tools, so each evaluation run now builds a fresh agent.

## Next steps (Phase 3)
- Record the demo video (multi-step purchase question and the tool-failure case).
- Write the 3–4 page report and contribution statements.
