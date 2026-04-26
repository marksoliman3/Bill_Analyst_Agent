# CLAUDE.md

## Project Overview

**Bill Analyst** is a multi-agent AI pipeline that analyzes U.S. legislative bills for relevance to AI policy across seven taxonomy dimensions. It reads bills from CSV, runs them through a LangGraph "Graph of Graphs" workflow, and outputs scored/justified results to CSV.

The system is part of the **CATS** (presumably a policy research initiative) project. It uses the OpenAI API (not Anthropic) via LangChain/LangGraph.

## How to Run

```bash
# Activate the existing venv (venv/ at project root, not checked into git)
source venv/bin/activate

# Set OPENAI_API_KEY in .env (already gitignored)

# Run the pipeline
python -m src.main
```

Input: `data/input/bills.csv` (must have `Bill_Number` and `Bill_Text` columns)
Output: `data/output/analysis_results.csv`
Logs: `data/output/logs/bill_analysis_<timestamp>.log`

These paths are configured in `src/config.py`. The `data/` directory is gitignored.

## Architecture

### Graph of Graphs (LangGraph)

The pipeline is orchestrated in `src/graph.py` as a LangGraph `StateGraph` using `AgentState` (defined in `src/state.py`). Before entering the graph, each bill passes through a cheap keyword pre-filter (see below). Bills that pass the filter are processed by the full agent pipeline:

```
[AI Keyword Pre-Filter] -> Extractor -> Summarizer -> Analyst_1 -> ... -> Analyst_7 -> Judge -> Consolidator -> END
                                                                                         |
                                                                                         v (if REVISE)
                                                                                  Analyst(s) needing revision -> Judge (loop)
```

0. **AI Keyword Pre-Filter** (`src/main.py`: `is_ai_related()`) - Regex-based gate that runs before the LangGraph pipeline. Bills must contain at least one AI-specific keyword (e.g., "artificial intelligence", "machine learning", "neural network", "deepfake", "AI") to proceed. Bills with 3+ keyword hits pass automatically. Bills with 1-2 hits are checked against incidental patterns (AI mentioned in a laundry list or cross-reference) and ceremonial patterns (commendations, memorials) — if either matches, the bill is filtered out. Filtered bills get `status: "filtered_not_ai"` with empty scores, saving API calls. On the full 1,532-bill dataset, this filters ~266 bills including ~154 that were previously over-scored by the LLM analysts (e.g., algorithmic rent pricing, intimate images, insurance telematics — bills that use words like "algorithm" but are not about AI).

1. **Extractor** (`src/agents/extractor.py`) - Parses raw bill text into relevant extracts. Uses `gpt-4o-mini`. Extracts sections relevant to the seven AI policy dimensions. Has fallback logic for minimal extractions.

2. **Summarizer** (`src/agents/summarizer.py`) - Produces a 5-sentence plain-language summary of the bill. Uses `gpt-4o-mini`.

3. **Analysts** (`src/agents/analysts.py`) - Seven specialized analyst agents, one per taxonomy dimension. All use `gpt-5-nano`. Each scores a bill on a **0 / 0.5 / 1 scale** with a justification. Analysts run **sequentially** (not in parallel). Analyst definitions live in `src/agents/configs/analysts_config.py`.

4. **Judge** (`src/agents/judge.py`) - Quality control agent that reviews all analyst scores against the bill text. Uses `gpt-5-nano`. Can AGREE (pass to finalize), request MULTI_ANALYST_REVISION (send specific analysts back with feedback), or FAIL_BILL. Max retry attempts controlled by `MAX_RETRY_ATTEMPTS` in config (currently 1).

5. **Consolidator** (`src/agents/consolidator.py`) - Aggregates all outputs into a final consolidated report. No LLM call -- pure Python aggregation. Missing analysts/scores surface as empty (no fallback values).

### State Management

`src/state.py` defines:
- `AgentState` (TypedDict) - The shared state flowing through the graph. Key fields: `bill_id`, `bill_text`, `bill_extracts`, `summary`, `analyst_results` (dict), `judgement`, `retry_attempts`, `analysts_needing_revision`, `consolidated_report`, `status`.
- Pydantic models for structured output parsing: `ExtractOutput`, `SummaryOutput`, `AnalystOutput`, `JudgeOutput`, `JudgementContent`.

### Revision Flow

The Judge can request revisions from specific analysts. The graph handles this via conditional routing:
- Judge sets `analysts_needing_revision` list and `feedback_by_analyst` dict in the judgement
- Graph routes to the first analyst needing revision, then chains through the rest
- Revised analysts get their feedback from `judgement.feedback_by_analyst` (single source of truth)
- After all revisions, flow returns to Judge for re-evaluation
- `processed_analysts` list prevents infinite loops within a revision cycle
- If any analyst hits `MAX_RETRY_ATTEMPTS`, the bill auto-passes to finalization

## The Seven Analyst Dimensions

All defined in `src/agents/configs/analysts_config.py`:

| Key | Dimension | Focus |
|-----|-----------|-------|
| `product_safety` | Product Safety, Accountability, & Risk | AI developer/vendor safety obligations (build-side only) |
| `property_rights` | Property Rights, Attribution, & Data | IP ownership, data-as-property, likeness rights, compensation |
| `market_structure` | Market Structure & Competition | Antitrust, competitive access, algorithmic collusion |
| `specific_use` | Specific Use & Sectoral Regulation | Sector-specific AI rules (healthcare, employment, deepfakes, etc.) |
| `societal_risks` | Existential and Societal Risks | Labor displacement, environment, election infrastructure, catastrophic risk |
| `institutional_processes` | Institutional Processes & Governance | Creation of oversight bodies, study mandates, regulatory sandboxes |
| `funding_economic` | Funding & Economic Development | Appropriations, tax incentives, workforce training funding |

Each analyst config has: `persona`, `scope` (with threshold questions and critical exclusions), `task_instructions`, `revision_instructions`, `scoring_rubric`, and `output_schema`.

### Scoring Rubric (shared)

- **0**: Not mentioned in the bill
- **0.5**: Moderately addressed (specific provisions but not primary focus)
- **1**: Strongly addressed (bill's central purpose)

## Key Files

```
src/
  main.py                              # Entry point. AI keyword pre-filter, iterates bills, invokes graph, merges results to output CSV
  graph.py                             # LangGraph orchestration. Builds the full graph with conditional routing
  state.py                             # AgentState TypedDict + Pydantic output models
  config.py                            # Env vars, file paths, retry settings, logging setup
  agents/
    extractor.py                       # Extractor subgraph (gpt-4o-mini)
    summarizer.py                      # Summarizer subgraph (gpt-4o-mini)
    analysts.py                        # Analyst factory + subgraphs (gpt-5-nano), JSON parsing, retry logic
    judge.py                           # Judge subgraph (gpt-5-nano)
    consolidator.py                    # Consolidator subgraph (no LLM)
    configs/
      analysts_config.py               # All 7 analyst definitions (persona, scope, instructions, rubric)
      nonanalysts_config.py            # Extractor, Summarizer, Judge definitions
  tools/
    file_io_tools.py                   # CSV read/write utilities (pandas)
```

## Conventions

- **LLM models**: Extractor and Summarizer use `gpt-4o-mini`. Analysts and Judge use `gpt-5-nano`. All at `temperature=0`.
- **Output format**: Analysts output `{score, justification}` as JSON. Judge outputs nested `{judgement: {decision, next_step, analysts_needing_revision, feedback_by_analyst}}`.
- **AI pre-filter keywords**: Defined in `AI_KEYWORDS`, `INCIDENTAL_PATTERNS`, and `CEREMONIAL_PATTERNS` at the top of `src/main.py`. The keyword list intentionally excludes broader tech terms like "algorithm", "automated system", "digital replica" — these trigger over-scoring on non-AI bills. Only AI-specific terms are included.
- **Error handling**: Analysts use `tenacity` retry with exponential backoff for transient OpenAI errors (500s, timeouts, rate limits). `SanitizedJsonOutputParser` handles malformed JSON from LLMs with `extract_json_from_text()` fallback. Parse failures trigger up to 3 re-prompts before giving up.
- **Score validation**: Scores are validated at multiple layers -- Pydantic validator in `AnalystOutput`, `SanitizedJsonOutputParser`, and `extract_score()` in main.py. Invalid scores are coerced to nearest valid value (0, 0.5, or 1).
- **Logging**: Every agent logs extensively with prefixes like `[AI_FILTER]`, `[EXTRACTOR]`, `[ANALYST:key]`, `[JUDGE]`, `[CONSOLIDATOR]`, `[GRAPH]`. Logs go to both console and timestamped file in `data/output/logs/`.
- **Config as single source of truth**: Agent prompts/personas are centralized in `analysts_config.py` and `nonanalysts_config.py`. The `analysts.py` factory reads these configs dynamically.
- **Output CSV**: Merges original input columns with analysis results. Individual score columns (e.g., `product_safety_score`) are extracted for easy filtering.

## Dependencies

Core: `langgraph`, `langchain`, `langchain-core`, `langchain-openai`, `pydantic`, `pandas`, `python-dotenv`
Retry: `tenacity` (used in analysts.py, not listed in requirements.txt)

## Data & Batch Workflow

The full dataset is 1,532 bills in `data/input/raw_full_bills_with_intro_dates.csv`. These are split into 4 batches (`bills_part_1.csv` through `bills_part_4.csv`) to keep run times manageable and reduce error risk. The workflow:

1. Rename the target batch file to `bills.csv` (e.g., `bills_part_1.csv` -> `bills.csv`). The config always reads from `data/input/bills.csv`.
2. Run the pipeline (`python -m src.main`)
3. Rename `bills.csv` back to its original name, and rename the output from `analysis_results.csv` to `analysis_results_1.csv` (matching the batch number)
4. Repeat for each batch
5. Concatenate the 4 result files into `Final_Database_<version>.csv`

Previous version outputs are archived in `data/output/Previous_Versions/`.

## Things to Know

- The `tests/` directory is outdated and not in use.
- `MemoryBank/` and `.clinerules/` are legacy context files from a previous AI assistant (Cline); they are gitignored and may be outdated.
- The `data/` directory (input CSVs, output CSVs, logs) is entirely gitignored.
- `test_openai_key.py` and `test_parser.py` in the project root are standalone test scripts, also gitignored.
- The graph is rebuilt and compiled fresh for each bill (`build_full_graph().compile()` inside the loop in main.py).
- Analysts run sequentially, not in parallel, due to how the graph chains them with conditional edges.
- The `feedback` field on `AgentState` is deprecated; `judgement.feedback_by_analyst` is the single source of truth for revision feedback.
