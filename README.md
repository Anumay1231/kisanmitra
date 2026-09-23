# KisanMitra 🚜: Tool-Augmented (Agentic) Dealership Assistant

PSIS Activity 2: *Build a Tool-Augmented/Agentic LLM Application*, B.Tech AI, MPSTME (2026–27)
Team: **I054 Anumay Pandey · I023 Yash Garg · I037 Yash Kothari**

## Problem
A tractor dealership answers the same questions all day: which machine fits a farmer's budget and land, what the EMI is after subsidy, whether a spare part is in stock, what a customer's machine was last serviced for, whether the next three days are dry enough to spray, and what a government scheme allows. The answers live in different places: a stock and service database, a weather service, a market price service, a subsidy PDF and a calculator. KisanMitra is an LLM **agent** that decides which of those sources to call, in what order, and combines them into one answer, without inventing any figure itself.

## Architecture
![architecture](docs/architecture_diagram.png)

The LLM receives the tool schemas. At each step it either emits a tool call (name + arguments) or a final answer. `AgentExecutor` runs the tool, appends the observation to `agent_scratchpad`, and calls the model again, up to 6 iterations.

| Tool | Type | What it provides |
|---|---|---|
| `get_weather_forecast` | Public REST API (Open-Meteo, no key) | Rain, temperature and wind forecast for a location |
| `get_mandi_price` | REST API (data.gov.in, free key) | Recent mandi prices per quintal |
| `search_inventory`, `search_service_records`, `check_part_stock` | SQLite database | Machines, prices, stock, service history, spare parts |
| `calculate_purchase_plan`, `estimate_operating_cost` | Deterministic Python | Subsidy, EMI, interest, diesel consumption and cost |
| `lookup_scheme_rules` | FAISS retriever over SMAM PDFs | Subsidy rules with file and page citations |

| LangChain component | Where |
|---|---|
| Tool / Agent | `@tool` functions with Pydantic arg schemas; `create_tool_calling_agent` + `AgentExecutor` |
| ChatPromptTemplate + MessagesPlaceholder | `prompts.py` (system rules, history, `agent_scratchpad`) |
| Memory | `RunnableWithMessageHistory` per session |
| LCEL composition | `SUMMARY_PROMPT \| llm \| PydanticOutputParser` summary chain |
| OutputParser | `AdviceCard` (recommendation, key figures, tools used, data gaps, confidence) |
| VectorStoreRetriever | FAISS retriever exposed as the `lookup_scheme_rules` tool |

## Repository layout
```
src/kisanmitra/   config, tools, knowledge (RAG tool), prompts, schema, agent
scripts/          seed_db.py, evaluate.py
tests/            fake_llm.py, test_agent_offline.py   (run without any API key)
eval/             test_scenarios.json, results.csv (generated)
notebooks/        KisanMitra_Agent.ipynb (self-contained Colab version)
docs/             architecture diagram, progress notes
app.py            Gradio chat UI
```

## Run
**Colab:** open `notebooks/KisanMitra_Agent.ipynb` → Runtime → Run all → paste a free Groq key.

**Local:**
```bash
pip install -r requirements.txt
export GROQ_API_KEY=...          # free from console.groq.com
export DATAGOV_API_KEY=...       # optional; without it the mandi tool returns TOOL_ERROR by design
python scripts/seed_db.py
python tests/test_agent_offline.py   # agent loop tests, no API key needed
python scripts/evaluate.py           # writes eval/results.csv
python app.py
```

## Evaluation
9 scenarios: single-tool database lookup, multi-step (inventory → EMI), memory follow-up, weather API, service history, fuel calculator, a deliberate tool failure (no mandi key), scheme lookup through the RAG tool, and an out-of-scope request that must be refused. Metrics: tool-selection correctness, error handling, tool calls per question, latency, and an independent Python re-computation of the EMI to verify the calculator's figure.

## Known limitations
- Tool choice depends on the model; an ambiguous question can trigger the wrong tool (seen in evaluation).
- The mandi dataset's commodity names must match exactly; a wrong name returns no records.
- Dealership data is synthetic; a real deployment would connect to the dealer management system read-only.
- English only, and the agent cannot write to the database (deliberately read-only).
