# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Evaluation framework for measuring agent quality across development stages
- Supabase migration for `news_articles` and `eval_runs` tables (`backend/migrations/001_news_and_eval_tables.sql`)
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
- Dead code: `buildReply()` and `buildPortfolioReply()` functions (replaced by agent endpoint)
- Dead code: unused `HoldingRow` component

## [Prior history]

See `git log` for changes before changelog was introduced.
