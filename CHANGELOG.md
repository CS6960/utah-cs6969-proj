# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed
- Extended NDJSON streaming to emit `stage` events carrying structured trace data (retriever start, Strategist draft, Critic review, revision) from the agent pipeline without modifying agent code. Frontend chat panels display live status labels ("Gathering evidence 12s", "Drafting analysis 28s", "Reviewing for risks 55s") during the long "Thinking…" wait. Intercepts the `logger.info("agent_trace %s", event)` call in `backend/agents.py` via a per-request logging handler filtered by a nonce on `threading.current_thread()` (safe against thread-pool reuse). Poll interval in the stream generator dropped from 10s to 1s so stage events surface promptly; heartbeats still fire at 10s intervals but only when no stage event has been emitted in that window.
- Replaced buffered JSON responses on `/api/agent` and `/api/report-agent` with NDJSON streaming and 10-second heartbeats. Total pipeline cap raised from 85s to 240s; heartbeat lines reset Render's ~100s edge-proxy idle timer so slow multi-stage agent runs no longer return 503. `X-Accel-Buffering: no` on the streaming response disables nginx buffering at the Render edge. Frontend `fetchAgentReply` now reads NDJSON line-by-line, ignores heartbeats, and wraps the final result event in a synthetic response-like object so existing `submitMessage` / `submitPortfolioMessage` call sites need no changes. Content-type guard on the reader preserves the existing cold-start 502 retry-with-warming UX for failures that happen before the stream starts.
- Chat suggestion chips are now hybrid — onboarding on empty conversations, inline follow-ups under the last advisor reply after the user engages. Reclaims ~60px of permanent header space in each panel. Shared `SuggestionChips` component replaces duplicated button markup in portfolio and holding panels.
- Chat scroll region grows from 260px to `min(60vh, 420px)` after the first user message, giving long advisor replies (Strategist + Dissent sections) meaningfully more vertical room on typical viewports while staying within 60% of viewport height on short screens.

### Removed
- Dead code in `frontend/src/App.jsx`: unused helpers `buildReply`, `buildPortfolioReply` (superseded by the `/api/agent` endpoint) and unused JSX components `StatChip`, `ListMetric`, `DetailBlock` (no call sites). Clears all five `no-unused-vars` ESLint errors.

### Fixed
- Chat bubbles no longer show `### Revision notes` / `### Dissenting perspective` with literal `###` prefixes or bare `---` as literal dashes — `markdownToHtml` now parses ATX headings and `<hr>` thematic breaks. The eval-judge delimiters `<!-- DISSENT_BLOCK_START_DO_NOT_SCORE -->` / `<!-- DISSENT_BLOCK_END -->` are stripped from advisor messages before rendering (raw API response unchanged; judge reads the raw string and is unaffected). A labeled separator — "End of recommendation. The sections below are Strategist revision notes and a devil's-advocate Critic review, included for transparency." — now appears above the Revision notes section so users can visually distinguish the recommendation from dev/eval material.
- Chat "Failed to fetch" / CORS errors on `https://cs6960.github.io/utah-cs6969-proj/`. Root cause was an HTTP 502 from Render's edge proxy (Cloudflare's 502 page drops `Access-Control-Allow-Origin`, which the browser reports as a CORS violation). `/api/agent` and `/api/report-agent` in `backend/app.py` now run `run_critic_agent` / `run_agent` inside `asyncio.wait_for` with an 85s cap (below Render's ~100s proxy timeout) and wrap both in `try/except` that raises `HTTPException(503)` on timeout or unhandled crash, guaranteeing responses always pass through the CORS middleware. Frontend `submitMessage` / `submitPortfolioMessage` in `frontend/src/App.jsx` now use a shared `fetchAgentReply(apiBase, query)` helper with `AbortController(110s)` and one automatic retry on 502/503/504/abort/network failure, with a "Backend is waking up, retrying in a few seconds..." UX during the retry. Added a warm-up `GET /api/health` that fires when either chat panel expands, triggering cold-start wake-up before the user types.

### Added
- `get_portfolio_weights()` helper in `backend/portfolio.py` returning per-position dollar weight as % of total NAV (equities + cash) and % of equity, sorted by weight descending. Computed from latest close × shares from `portfolio_positions` + `portfolio_cash`. Fixes Phase 3 human-eval defect where Q1/Q2 reported concentration as "5 of 8 holdings" instead of portfolio weight.
- `build_portfolio_context()` now appends a POSITION WEIGHTS block (per-position $ and %, equity vs cash split, total NAV) plus a CONCENTRATION FRAMING directive instructing the LLM to express concentration in % of NAV, not position count. Context flows to Retriever system prompt, Strategist draft, Critic, and Strategist revision — all four stages see weights without needing a tool call.
- Extended `stock_prices` coverage through 2026-04-02 (16 new rows for AAPL, MSFT, JPM, NVDA, AMZN, GOOGL, LLY, XOM on Apr 1 + Apr 2 via yfinance). Prices now align with news corpus window (Mar 13 – Apr 2). Required because news extends through Apr 2 but prior price corpus ended Mar 31, causing the agent to cite "future-dated" news (Apr 2) that had no matching price action. New latest close date is 2026-04-02; portfolio NAV updated from $63,344.54 → $63,634.92.

### Changed
- Cleaned up stale `meta/llama-3.1-70b-instruct` fallback defaults in `backend/agents.py` and `script/build_graph.py` — both now default to `qwen/qwen3.5-122b-a10b`, which matches the `MODEL_NAME` env value the project has been running on. In practice the fallbacks never fired when `.env` was loaded, but they were misleading in the source. Also updated the Llama-specific rationale comment in `backend/agent_tools/strategist_tools.py::serialize_for_llm` to describe the markdown-vs-JSON design in model-agnostic terms.
- `docs/08-AGENTS-TOOLS.md` now opens with a **Final Design (post-Phase 4)** section: one authoritative snapshot of the production pipeline (ASCII flow diagram from `/api/agent` through Retriever / evidence assembly / Strategist-draft / Critic / primary-vs-derived pre-filter / Strategist-revision / dissent-block embed), the POSITION WEIGHTS-augmented portfolio context, the full guardrail table (evidence-only citations, portfolio universe filter, cost-basis-aware trims, concentration framing, primary-vs-derived, dominant-driver, GAPS/ERRORS acknowledgment), the dissent-block delimiter contract, and the data-source table (holdings, cash, prices, news, filings, graph). Per-phase historical sections are preserved below as the evolution narrative.
- Strategist draft + revision prompts now include a COST-BASIS-AWARE TRIMS rule requiring trim / de-risk / profit-take recommendations to reason from each candidate position's unrealized P/L `(shares * (price - avgCost))` and weight (both available in `PORTFOLIO CONTEXT`). Prefer taking gains on positions with large unrealized gains; for positions near or below cost basis, propose tight stop-losses just below breakeven instead of outright trims. Blanket sector-weight targets ("reduce tech to 30% of NAV") without per-position cost-basis reasoning are rejected as insufficient. Addresses Phase 4 human-eval Q2 feedback: the agent had data (avgCost, current price) in portfolio context but was recommending flat sector-weight trims without using it.
- Eval rubric (`script/run_eval.py`) reframed from "March 24-31, 2026" window to "March 24 – April 2, 2026" window to match corpus coverage. `GROUND_TRUTH` rewritten in weight-framing terms (e.g. "~45% of NAV in tech") instead of count-based ("5 of 8 holdings"), removing the judge incentive that previously rewarded count-based framing and punished the post-weights-injection agent. `TEMPORAL_FACTS` now includes April 2 events (Dimon Hormuz warning, >50% oil surge, Hormuz traffic-protocol de-escalation signal, Bloomberg bonds selloff, Foundayo GLP-1 catalyst) and the Apr 1-2 tape (tech rebound + XOM pullback). `RELATIONAL_CONNECTIONS` updated to reflect partial de-escalation dynamic.
- Phase 4 methodological findings at `internal/phase4_limitations.md`: the grounded adversarial Critic conflicts with the static-rubric LLM-as-judge (which scores narrative similarity to ground-truth paragraphs, not evidence fidelity). Phase 4 code shipped; `docs/11-PIPELINE-PLAN.md` Phase 4 status remains PLANNED pending rubric redesign. Eval transcripts at `internal/eval_critic_20260416-070915.md` (v1 avg 2.3) and `internal/eval_critic_20260416-081412.md` (v2 avg 2.6) document the regression vs Phase 3 baseline 4.9 and the five rubric-design recommendations for future work.
- Critic prompt rules: PRIMARY-VS-DERIVED (do not rebut macro claims with derived equity prices) and DOMINANT-DRIVER (do not elevate secondary news over dominant macro driver in ALTERNATIVE_HYPOTHESES)
- Strategist-revision prompt rules: DOMINANCE PRESERVATION and PORTFOLIO UNIVERSE FILTER (non-portfolio tickers may appear only inside verbatim quoted evidence, never as recommendation subjects)
- `_tag_primary_vs_derived_challenges(dissent_text)` code-level pre-filter: annotates CHALLENGES entries that cite a portfolio equity's small-percent move as counter-evidence to a macro claim with `[AUTO-FILTERED: primary-vs-derived pattern — revision MUST REJECT]` before sending to revision. Original dissent preserved for user-facing response.
- HTML-comment delimiter around the dissent embed in `data.result` (`<!-- DISSENT_BLOCK_START_DO_NOT_SCORE --> … <!-- DISSENT_BLOCK_END -->`) so the eval judge can strip the Critic's output before scoring while the frontend still receives the full dissent text.
- `_strip_dissent_block(response)` in `script/run_eval.py`: strips the dissent delimiter block from `data.result` before feeding to the LLM judge so the judge scores only the revised recommendation (v2), not v2+dissent.
- Smoke test M-CRITIC strengthened assertions: top-level `dissent` key presence, `DISSENT_BLOCK_START_DO_NOT_SCORE` marker in `result`, `### Dissenting perspective` header present, dissent ≥200 chars.
- Phase 4 `run_critic_agent(query)` orchestrator in `backend/agents.py`: Retriever tool-loop → deterministic `_assemble_evidence_package` → Strategist-draft (tool-free) → Critic (tool-free, `temperature=0.85`) → Strategist-revision (tool-free, skip guard when no challenges)
- `_assemble_evidence_package(messages)` helper: joins ToolMessage content via `tool_call_id` into numbered `## Tool call N — <name>(<args>)` sections with an evidence-coverage header (counts by tool type and error count)
- `_parse_critic_challenges(dissent_text)` tolerant parser: counts enumerated CHALLENGES entries; returns 0 when none are found or only the "no material challenges identified" placeholder is present
- Evidence-identity sentinel: `evidence_for_draft` and `evidence_for_critic` reference the same string object so both downstream calls see identical data
- Empty-evidence short-circuit: if `_assemble_evidence_package` returns an empty string, `run_critic_agent` returns immediately with a sentinel message and skips all three downstream LLM calls
- Empty-Critic skip guard: if `_parse_critic_challenges` returns 0, Strategist-revision is skipped and `draft_v1` is used as the final result unchanged
- New trace event types emitted by `run_critic_agent`: `llm_started`, `llm_completed`, `llm_skipped`, `pipeline_short_circuit`, `result_length_warning`
- `/api/agent` response now includes top-level `dissent` and `draft` keys in addition to `result`; `result` embeds the Critic's output under a `### Dissenting perspective` header separated by `---`
- `script/smoke_test.py` `run_m_critic()` milestone: asserts `data.dissent` non-empty (≥200 chars), `data.draft` is a string, `### Dissenting perspective` present in `data.result`, and at least one underlying data tool in `tools_called`; gated behind `--include-critic` CLI flag
- Phase 3 entity-relationship graph: `entity_relationships` Supabase table (migration 003) storing pre-extracted causal edges from the news corpus
- Graph extraction script (`script/build_graph.py`) using LLM to extract entity-relationship triples from relevant news articles, with `--dry-run` and `--validate` flags
- `traverse_entity_graph()` in `backend/agent_tools/graph_tools.py` — 2-query hop pattern (SB003-compliant) for graph traversal at inference time
- `request_graph` Strategist tool wrapping `traverse_entity_graph` with GRAPH_CONNECTIONS serialization in `serialize_for_llm`
- `ToolCallLimitMiddleware(tool_name="request_graph", run_limit=2)` middleware for the Strategist agent

### Changed
- `strategist_agent` renamed to `retriever_agent`; system prompt rewritten as `RETRIEVER_AGENT_PROMPT` (gather-evidence-only, no synthesis, no recommendations); the Retriever's final AIMessage is discarded by `run_critic_agent` after evidence assembly
- `AGENTS["financial_advisor"]` now aliases `retriever_agent`; `/api/agent` bypasses `AGENTS` entirely and calls `run_critic_agent` directly
- `/api/agent` response shape: `result` now concatenates the Strategist-revision with a `### Dissenting perspective` section (separator `---`); new top-level `dissent` and `draft` keys added. Programmatic consumers expecting a single-voice response should split on `---` or read the `dissent` key directly
- `script/smoke_test.py` per-milestone `requests.post` timeouts raised 180 → 240 s to accommodate the 3-LLM-call Phase 4 pipeline
- `script/smoke_test.py` `ALPHABET_RISK_PHRASES` recalibrated for post-revision GOOGL vocabulary: `["Google Cloud", "YouTube", "Google Search", "antitrust", "artificial intelligence", "GOOGL"]`
- `script/smoke_test.py` M-RAG milestone now gated behind `--include-rag` (previously ran unconditionally)
- `ModelCallLimitMiddleware(run_limit=12)` (was 8) to accommodate the additional request_graph tool
- `STRATEGIST_AGENT_PROMPT` updated with request_graph in WORKFLOW and TOOL DESCRIPTIONS sections
- Smoke test `DATA_TOOLS` set now includes `traverse_entity_graph`

### Removed
- Dead `financial_advisor_agent` and its ungrounded sub-tools `call_skeptic_response` / `call_visionary_response` (backend/agents.py) — superseded by the grounded three-role pipeline
- Orphan `call_financial_reports_retrieval_agent` wrapper (its only consumer was the deleted `financial_advisor_agent`); `financial_reports_retrieval_agent` itself is preserved for `/api/report-agent`
- Dead `retriever_agent` create_agent scaffold and `RETRIEVER_SYSTEM_PROMPT` / `STRATEGIST_SYSTEM_PROMPT` string constants (replaced by `RETRIEVER_AGENT_PROMPT`)
- Dead `BASE_ADVISOR_TOOLS`, `RETRIEVER_TOOLS`, `ADVISOR_TOOLS`, `REPORT_TOOLS` lists from `backend/agent_tools/tools.py`; `REPORT_RETRIEVAL_TOOLS` is preserved for `/api/report-agent`
- `get_portfolio_holdings`, `get_stock_price`, `get_stock_price_history` tool functions from `backend/agent_tools/tools.py` (only referenced by deleted code); `calculator` is preserved in `REPORT_RETRIEVAL_TOOLS`

### Fixed
- Q3 eval gap: Strategist prompt now instructs weighing both short-term price action AND overall position P&L (current price vs average cost basis)
- Q4 eval gap: Strategist prompt now instructs considering new positions outside current portfolio when recommending cash deployment

### Changed
- All agent system prompts (Strategist, Retriever, Financial Advisor) now instruct the LLM to use Denver time (America/Denver) for dates and times in reports
- `script/run_eval.py` timestamps use explicit Denver timezone instead of naive `datetime.now()`
- Added Timezone Convention section to CLAUDE.md

### Fixed
- News article body never serialized to LLM context — `serialize_for_llm` rendered headline-only for NEWS section, so the Strategist could not read article content (Iran war details, oil dynamics, IRGC list). Now includes truncated body (≤600 chars) indented under each headline.
- `request_news` article limit increased from 15 to 40 — with 73 of 90 articles sharing the same date, the top 15 by `published_at DESC` excluded all Iran/geopolitical articles (first appeared at position 16). Critical "Jamie Dimon Flags Iran Conflict" article was at position 30.

### Changed
- `STRATEGIST_AGENT_PROMPT` rewritten to close Phase 2 eval gaps (G=2.75→?, R=1.25→?):
  - `request_news` now mandatory and called FIRST (was optional step 6; Q1/Q2 skipped it entirely)
  - Added "SYNTHESIS — Cross-Sector Causal Reasoning" section requiring the agent to trace macro events through multiple holdings, identify inverse dynamics, and connect price moves to specific news catalysts
  - Tool call order: news → prices → filings (news-informed filing scope)
  - `request_news` tool description updated to mention article summaries (not just headlines)

### Added
- Strategist-orchestrated agent (`backend/agent_tools/strategist_tools.py`) with typed `EvidenceResponse` contract including non-optional `gaps` and `errors` fields that surface infrastructure failures directly into the Strategist's context
- Three Strategist tools: `request_filings(scope, tickers)`, `request_prices(tickers, start_date, end_date)`, `request_news(scope, tickers)`
- `run_strategist_agent(query)` in `backend/agents.py` returning `(response, tools_called, execution_trace)` — drop-in shape-compatible with `run_agent`
- `STRATEGIST_AGENT_PROMPT` drafted in `backend/agents.py` with explicit workflow, GAPS/ERRORS acknowledgment contract, noise-ticker allow-list, and 1500-word ceiling
- Real `request_news` tool (`backend/agent_tools/news_tools.py`) backed by `news_articles` Supabase table (90 articles, 80 relevant + 10 noise). Does NOT filter by `relevant` — agent must demonstrate noise filtering. `request_news` run_limit raised from 1 to 2. Strategist prompt updated to instruct noise-aware citation.
- Hard caps via LangChain middleware: `ModelCallLimitMiddleware(run_limit=8)`, `ToolCallLimitMiddleware(run_limit=2)` for filings/prices/news
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
- **Phase 2 Tree-RAG rebuild**: replaced broken TOC-page-number parser (`script/test_10k_llm_nvd.py`, removed via `git rm`) with edgartools-based ingest at `backend/scripts/ingest_10k_filings.py`. Full re-embed of all 8 portfolio 10-Ks (AAPL, MSFT, GOOGL, AMZN, NVDA, LLY, JPM, XOM). Two-phase atomic-or-nothing commit: Phase A builds all 8 payloads in-memory, Phase B runs a schema probe, bulk DELETE of 18 old+new `file_title` strings, per-ticker INSERT with completeness gate, cross-ticker coverage gate (≥7 of 8 tickers on unfiltered "risk factors" top_k=8), `rollback_all()` on any exception. Unfiltered "risk factors" top_k=8 coverage improves from 3 of 8 to ≥7 of 8 tickers. Schema and `match_document_tree_nodes` RPC contract unchanged — Phase 1b gate criteria remain valid.
  - Corrected `docs/08-SUPABASE-FREE-TIER.md` payload math: 3072 → 4096 dims, 24 KB → 32 KB per row, 14 MB → 19 MB per 600-node filing, 26 MB per ~800-node filing.
- **Phase 2 validation harness** at `script/validate_10k_rag.py`: 32-cell content matrix (8 tickers × 4 scopes: risk factors, MD&A, revenue segments, competition). Exits 0 only if all 32 cells pass content-level keyword and regex assertions.
- **Phase 2 smoke test** added `run_m_rag()` to `script/smoke_test.py` targeting GOOGL (current worst-case ticker), gated behind `--include-rag` flag during the scaffold phase.
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
- `script/test_10k_llm_nvd.py` and `script/test_10k_llm_nvd.ipynb` — broken TOC-page-number parser, superseded by the edgartools-based ingest at `backend/scripts/ingest_10k_filings.py`. Recovery path: `git show HEAD~1:script/test_10k_llm_nvd.py > /tmp/test_10k_llm_nvd.py` (adjust `HEAD~N` depending on commit order).
- `backend/pipeline.py` (dead code — zero importers verified; its `EvidencePackage` dataclass was shadowed by the new `EvidenceResponse` type)
- Q5 "What is the operating margin for Nvida?" from `script/run_eval.py` `PRESET_QUESTIONS` (never had ground truth, always scored 0, trivially satisfied acceptance criteria)
- Dead code: `buildReply()` and `buildPortfolioReply()` functions (replaced by agent endpoint)
- Dead code: unused `HoldingRow` component

## [Prior history]

See `git log` for changes before changelog was introduced.
