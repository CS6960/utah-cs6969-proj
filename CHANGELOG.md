# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Strategist-orchestrated agent (`backend/agent_tools/strategist_tools.py`) with typed `EvidenceResponse` contract including non-optional `gaps` and `errors` fields that surface infrastructure failures directly into the Strategist's context
- Three Strategist tools: `request_filings(scope, tickers)`, `request_prices(tickers, start_date, end_date)`, `request_news(scope, tickers)` (Phase 2 stub)
- `run_strategist_agent(query)` in `backend/agents.py` returning `(response, tools_called, execution_trace)` — drop-in shape-compatible with `run_agent`
- `STRATEGIST_AGENT_PROMPT` drafted in `backend/agents.py` with explicit workflow, GAPS/ERRORS acknowledgment contract, noise-ticker allow-list, and 1500-word ceiling
- Hard caps via LangChain middleware: `ModelCallLimitMiddleware(run_limit=8)`, `ToolCallLimitMiddleware(run_limit=2)` for filings/prices, `run_limit=1` for news
- `_RAG_COUNTER` ContextVar defense-in-depth RAG ceiling (≤3 per request) re-mitigating the 2026-04-03 Supabase fan-out incident
- Phase 1b architectural memo at `internal/phase1b_agent_pivot.md` (gitignored) documenting the sequential-pipeline → Strategist-orchestrated pivot
- Phase 1b section in `docs/11-PIPELINE-PLAN.md`; updated architecture diagrams in `docs/08-AGENTS-TOOLS.md`
- `backend/_env_bootstrap.py` — import-time `load_dotenv` shim imported by `agents.py`, `portfolio.py`, `stock_prices.py`, and `agent_tools/financial_reports_tools.py` so `backend/venv/bin/python -c "import agents"` works without a `source venv/bin/activate && source .env` preamble
- CLAUDE.md guidance sections: "Running backend Python and ruff without permission prompts" (use `backend/venv/bin/python` / `backend/venv/bin/ruff` directly) and "Running git in a worktree without permission prompts" (use `git -C <path>` instead of `cd <path> && git`)
- `get_stock_price_history` retriever tool and `get_price_history_for_symbol(s)` helpers in `backend/stock_prices.py` for date-range daily close queries against Supabase
- Pipeline deterministic fallback now batch-fetches daily closes for all holdings in a single Supabase call and emits a `PRICE HISTORY` evidence block with weekly % change
- Milestone 2 report (`internal/milestone2.tex`) with evaluation framework results, Phase 0/1 comparison, human feedback findings, and news data structure
- Bibliography file (`internal/references.bib`) with all cited references including LLM-as-judge
- Supabase free-tier coding rules documentation (`docs/08-SUPABASE-FREE-TIER.md`)
- Pre-commit linter (`script/check_supabase_rules.py`) enforcing 6 Supabase query safety rules (SB001–SB006)
- Git pre-commit hook wired to lint staged Python files against Supabase rules
- Supabase constraints summary in CLAUDE.md for AI-assisted development
- Phase 1 data requirements in pipeline plan: historical prices (March 24–31) and 4 missing 10-K filings (AMZN, GOOGL, LLY, XOM)
- Pipeline orchestrator (`backend/pipeline.py`) with Retriever → Strategist 2-agent pipeline
- Retriever agent with SEC filing tools and deterministic fallback for tool-call failures
- Strategist agent as direct LLM call for evidence synthesis
- `RETRIEVER_TOOLS` list in `backend/agent_tools/tools.py`
- `EvidencePackage` dataclass for structured evidence passing between pipeline stages
- Per-stage logging with timestamps in pipeline orchestrator
- Temporal Precision scoring dimension (1–5) to evaluation rubric with per-question date-stamped ground truth facts
- Relational Recall scoring dimension (1–5) to evaluation rubric with per-question cross-sector causal chain annotations
- `graph` evaluation stage between `news_agent` and `critic` to isolate LazyGraphRAG contribution
- Noise citation detection: eval runner flags non-portfolio tickers (TSLA, PFE, etc.) in agent responses
- Tool usage tracking: backend returns `tools_called` from agent runs, eval stores and reports tool usage per stage
- Migration `002_eval_schema_update.sql` adding `temporal_precision`, `relational_recall`, `noise_citations`, `noise_citation_count` to `eval_runs`
- Pipeline implementation plan with 4 phases, gate criteria, and status tracking (`docs/11-PIPELINE-PLAN.md`)
- Phase status tables in `docs/08-AGENTS-TOOLS.md`, `docs/09-EVALUATION.md`, and `internal/evaluation_methodology.md`
- Gate criteria for each phase transition documented in all three docs

### Fixed
- Milestone 2 cash-exclusion bug: `build_portfolio_context()` now reads `data.get("cashBalances")` and renders a `CASH BALANCES:` section. Previously, cash was silently omitted from the Strategist's context, causing percentage-based portfolio math to be systematically wrong (Q2 "Am I diversified?" scored low for this exact reason)
- SB004: Moved `create_client()` from per-function calls to module-level singletons in `backend/portfolio.py`, `backend/stock_prices.py`, and `backend/agent_tools/financial_reports_tools.py` to prevent connection churn on the free tier
- SB001: Added `.limit(50)` to unbounded `stock_prices` and `document_tree_nodes` select queries to prevent free-tier statement timeouts
- SB001: Added `.limit(50)` to `get_latest_close_prices_for_symbols` select in `backend/stock_prices.py` and to `_get_latest_prices_for_symbols` select in `backend/portfolio.py`
- Retriever had no way to cite day-over-day price moves — historical CSV was seeded but no tool queried it; added `get_stock_price_history` and wired it into the retriever prompt and fallback

### Changed
- `/api/agent` now routes through `run_strategist_agent()` instead of the regression-routed `financial_advisor_agent`. Response shape `(result, tools_called, execution_trace)` unchanged so the frontend is unaffected
- `AGENTS["financial_advisor"]` now points at `strategist_agent`. The `financial_advisor_agent` Python object is retained in `agents.py` for a future Phase 4 cleanup but is unreachable via `/api/agent`
- `docs/08-SUPABASE-FREE-TIER.md` incident log: 2026-04-03 RAG fan-out entry now cites the Phase 1b `_RAG_COUNTER` + `ToolCallLimitMiddleware` mitigation
- `/api/agent` now routes through pipeline for default `financial_advisor` role
- Extracted `extract_tools_called()` helper from `run_agent()` for reuse in pipeline
- `run_agent()` now returns `(response, tools_called)` tuple instead of just `response`
- `/api/agent` and `/api/report-agent` endpoints now include `tools_called` in response JSON
- LLM judge prompt expanded from 3 to 5 scoring dimensions with temporal facts and relational connections as additional context
- Eval report table now shows all 5 dimensions, noise citation count, and tool usage ratio
- `--stage` argument now validates against the canonical stage list

### Fixed
- `tools_called` was always stored as empty list; backend now extracts tool names from LangChain intermediate messages

- Evaluation framework for measuring agent quality across development stages
- Supabase migration for `news_articles` and `eval_runs` tables (`backend/supabase/migrations/001_news_and_eval_tables.sql`)
- News seeding script with support for relevant and noise articles (`script/seed_news.py`)
- Baseline evaluation runner with LLM-as-judge scoring (`script/run_eval.py`)
- March 24–31, 2026 market analysis with ground truth answers (`internal/march_24_31_analysis.md`)
- Evaluation methodology documentation (`internal/evaluation_methodology.md`, `docs/09-EVALUATION.md`)
- News corpus documentation (`docs/10-NEWS-CORPUS.md`)
- Supabase credentials added to backend `.env.example`

- Embedded fallback portfolio data for instant first paint (`frontend/src/fallbackHoldings.js`)
- `<link rel="preconnect">` to Render backend in `index.html` for early TCP/TLS handshake
- `VITE_API_BASE` env var override restored in `chatApiBase` detection
- Staleness indicator showing "Prices as of ..." when displaying fallback data
- ESLint with React plugins configured (`eslint.config.js`, `npm run lint`)
- Ruff linter + formatter configured for backend (`ruff.toml`, `ruff check .`, `ruff format .`)
- CHANGELOG.md for tracking project changes

### Changed
- Portfolio polling interval reduced from 60s to 300s (backend serves static CSV; frequent polling wastes cold-start budget)
- Holdings subtitle updates dynamically to reflect last price update time
- Loading gate now only shows when holdings array is empty AND no fallback data is available

### Fixed
- StatChip components no longer display $0.00 / +0.0% during initial load (holdings pre-seeded with fallback data)
- `VITE_API_BASE` env var was missing from `chatApiBase` memo after prior refactor
- `==` replaced with strict equality (`===`) for `dayChangePct` null check

### Removed
- `backend/pipeline.py` (dead code — zero importers verified; its `EvidencePackage` dataclass was shadowed by the new `EvidenceResponse` type)
- Q5 "What is the operating margin for Nvida?" from `script/run_eval.py` `PRESET_QUESTIONS` (never had ground truth, always scored 0, trivially satisfied acceptance criteria)
- Dead code: `buildReply()` and `buildPortfolioReply()` functions (replaced by agent endpoint)
- Dead code: unused `HoldingRow` component

## [Prior history]

See `git log` for changes before changelog was introduced.
