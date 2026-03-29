# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
npm run dev       # Start Vite dev server with HMR
npm run build     # Production build to dist/
npm run preview   # Serve production build locally
npm test          # Testing
```
## Changelog

All changes must be logged in `CHANGELOG.md` at the project root. Follow [Keep a Changelog](https://keepachangelog.com/) format. When completing a feature, bug fix, or refactor, add an entry under `[Unreleased]` with the appropriate category (Added, Changed, Fixed, Removed). Move entries to a versioned section when cutting a release.

## TODO
No test runner is configured yet. ESLint is available via `npx eslint`.

## Workflow

1. Create feature branch from `main`
2. Write tests first
3. Implement feature
4. Open PR with description

## Boundaries

**Always:**
- Run tests before committing
- Use TypeScript strict mode

**Ask first:**
- Changes to `/migrations`
- Modifying public APIs

**Never:**
- Commit secrets or credentials
- Delete failing tests

## Known Gotchas

*Add lessons learned here as you encounter them*

## Project Overview

**Meridian** is an equity portfolio management dashboard for a ~$1M portfolio across 200–300 positions, managed by multiple teams using fundamental, systematic, and macroeconomic strategies. The frontend is a single-page React app with six tabbed modules.

## Architecture

### Current State: Monolithic Single-File React App

The entire UI lives in `src/App.jsx` (~460 lines, heavily minified). It is a single `export default function App()` component with all data, sub-components, and logic inline. There is no backend — all data is hardcoded mock data within the file.

**Stack:** Vite + React 19 + recharts (charting library). No state management library, no router, no CSS framework. All styling is inline via style objects.

### Key Code Patterns in App.jsx

- **Design tokens:** `T` object holds all colors. `M`/`S`/`SE` are font-family strings (IBM Plex Mono / Instrument Sans / Source Serif 4). Google Fonts loaded via `<link>` in the JSX.
- **Utility functions:** `pc(v)` = pos/neg color, `pp(v)` = plus prefix, `fm(n,d)` = number format, `fK(n)` = currency format ($K/$M).
- **Reusable components (defined inside the file):** `Stat` (KPI card), `Panel` (section container with title/subtitle/accent bar), `Tog` (toggle button group), `CTip` (recharts tooltip), `TreeMap` (custom heatmap), `SH` (sortable table header).
- **Mock data constants:** `PF` (portfolio KPIs), `AYTD_CURVE`/`MAX_CURVE` (return series), `SECTORS`, `TREE` (treemap positions), `ALL_POS` (full position list), `CLOSED` (trade log), `ALERTS`, `TEAMS`, `STRATEGIES`, `ATTRIBUTION`.
- **Tab routing:** `tab` state variable switches between `"weekly"`, `"risk"`, `"construction"`, `"closed"`, `"alerts"`, `"managers"` — each renders a different section via conditional `{tab === "weekly" && (...)}`.

### Six Modules (Tabs)

| Tab ID | Module | Key Visualizations |
|--------|--------|--------------------|
| `weekly` | Weekly Review | KPI strip, area chart (portfolio vs SPY), alert preview, treemap heatmap, top/bottom movers |
| `risk` | Risk Analytics | VaR/CVaR strip, return histogram, drawdown area chart, correlation matrix, rolling metrics table, factor bar chart |
| `construction` | Construction | Sector/factor drift tables, what-if staging form, radar chart, diversification metrics, trim/add candidates, full position table |
| `closed` | Closed Positions | Summary stats, trade log table, return waterfall, hold-vs-return scatter, exit analysis, lessons panel |
| `alerts` | Alerts & Attention | Category filter cards, alert feed with severity badges, severity summary, focus list, threshold reference |
| `managers` | Manager Performance | Team cards, team selector, strategy table, strategy detail with return chart + reconstruction timeline, attribution tables |

## Specification Documents

Detailed specs for each module live in `docs/`:

- `00-OVERVIEW.md` — Global config, database schema, all 28 API endpoints, external data dependencies
- `01-WEEKLY-REVIEW.md` through `06-MANAGER-PERFORMANCE.md` — Per-module specs including exact field definitions, computation formulas, color scales, severity thresholds, and frontend state variables

These docs define the target system (including a backend API and relational DB) that the current frontend prototype is designed against. The original monolithic JSX prototype is also preserved at `docs/portfolio-v5.jsx`.

## Domain Concepts

- **AYTD**: Annualized Year-to-Date, resets Sep 1 (academic year convention)
- **Strategy types**: Fundamental (single position), Systematic (multi-position basket, periodic reconstruction), Macroeconomic (multi-position basket, event-driven)
- **Reconstruction**: A rebalancing event within a strategy where positions are rotated in/out — not a new strategy
- **Manager teams**: Alpha Equity, Quant Systems, Macro Themes — each owns multiple strategies
- **Hierarchy**: Portfolio → Manager Team → Strategy → Position(s)
