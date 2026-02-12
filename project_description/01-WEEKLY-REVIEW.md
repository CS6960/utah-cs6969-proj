# Module 1: Weekly Review

## Purpose

The Weekly Review is the portfolio manager's operational heartbeat — the first screen they see each session. It answers: "How am I doing right now, what moved, and what needs attention?" It is optimized for a 2-minute Monday morning scan, not deep analysis.

---

## 1.1 KPI Strip

**Visual**: Seven metric cards in a single horizontal row.

| Card | Label | Value Example | Sub-value | Color Logic |
|------|-------|--------------|-----------|-------------|
| 1 | NAV | `$1.02M` | `−0.81% wk` | Default (neutral) |
| 2 | Cash | `$48.3K` | `4.7%` (% of NAV) | Default (neutral) |
| 3 | Positions | `247` | `of 300` | Default (neutral) |
| 4 | Week | `−0.81%` | `$8,291.44` | Red if negative, green if positive |
| 5 | Month | `+2.14%` | — | Red/green by sign |
| 6 | YTD | `+7.03%` | — | Red/green by sign |
| 7 | AYTD | `+9.57%` | `Since Sep 1` | Red/green by sign |

### Data Requirements

**NAV (Net Asset Value)**:
- Formula: `SUM(current_market_value for all open positions) + cash_balance`
- Source: `positions` table joined with latest prices from market data. Cash from `portfolio_snapshots` or a cash ledger.

**Cash**:
- Source: Dedicated `cash_balance` field in `portfolio_snapshots`, or derived from `NAV - SUM(position_values)`.
- The sub-value is `cash / NAV * 100`.

**Positions**:
- Formula: `COUNT(DISTINCT ticker) WHERE status = 'open'` from the `positions` table.
- The "of 300" limit comes from `portfolio_settings.max_positions`.

**Week P&L**:
- Formula: `(NAV_today - NAV_5_trading_days_ago) / NAV_5_trading_days_ago * 100`
- Requires: `portfolio_snapshots` table with daily NAV. Look back to the most recent Friday close (or last trading day of prior week).
- Dollar sub-value: `NAV_today - NAV_5_trading_days_ago`

**Month P&L**:
- Formula: `(NAV_today - NAV_first_day_of_month) / NAV_first_day_of_month * 100`
- Requires: `portfolio_snapshots` lookup for first trading day of current calendar month.

**YTD P&L**:
- Formula: `(NAV_today - NAV_dec31_prior_year) / NAV_dec31_prior_year * 100`
- Requires: `portfolio_snapshots` lookup for last trading day of prior year (Dec 31 or nearest).

**AYTD P&L**:
- Formula: `(NAV_today - NAV_at_aytd_start) / NAV_at_aytd_start * 100`
- The reset date defaults to September 1 (configurable in `portfolio_settings.aytd_start_date`).
- Requires: `portfolio_snapshots` lookup for the trading day on or just after the AYTD start date.
- The sub-value shows the reset date for context: `"Since Sep 1"`.

### Backend Computation

```
GET /api/weekly/kpi

Response:
{
  nav: number,              // Current portfolio NAV in dollars
  cash: number,             // Cash balance in dollars
  cash_pct: number,         // Cash as % of NAV
  position_count: number,   // Open position count
  max_positions: number,    // From settings
  week_pnl_pct: number,    // Week return %
  week_pnl_dollar: number, // Week P&L in dollars
  month_pnl_pct: number,   // Month return %
  ytd_pnl_pct: number,     // YTD return %
  ytd_pnl_dollar: number,  // YTD P&L in dollars
  aytd_pnl_pct: number,    // AYTD return %
  aytd_start_date: string, // ISO date, from settings
}
```

### Database Tables Involved

- `portfolio_snapshots` (nav, cash, date) — for historical NAV lookups
- `positions` (status, current_value) — for live NAV and position count
- `portfolio_settings` (aytd_start_date, max_positions)

---

## 1.2 Rate of Return Chart

**Visual**: Area chart with two series — Portfolio index (filled area) and SPY benchmark index (dashed line). Both rebased to 100 at a reference date.

**Toggle**: `AYTD` / `Max`
- **AYTD mode**: X-axis = monthly labels (Sep, Oct, Nov, Dec, Jan, Feb). Base date = `portfolio_settings.aytd_start_date`. Shows the current AYTD period only.
- **Max mode**: X-axis = annual/quarterly labels (2024-09, 2024-12, ..., 2026-02). Base date = `portfolio_settings.inception_date`. Shows full fund history.

### Data Requirements

**Portfolio Return Index**:
- Formula: For each date `d`, `index_d = 100 * (NAV_d / NAV_base_date)`
- This is a *total return index*, not just price. It includes dividends and cash flows.
- Computed from `portfolio_snapshots.nav` time series.

**SPY Benchmark Index**:
- Formula: For each date `d`, `spy_index_d = 100 * (SPY_close_d / SPY_close_base_date)`
- Source: `benchmark_snapshots` table or direct market data lookup for SPY adjusted close prices.

**Granularity**:
- AYTD mode: One data point per month-end (approximately 6 points for a Sep-to-Feb period).
- Max mode: One data point per quarter-end (approximately 7–10 points for a 1–2 year fund).

**Summary line below chart**:
- Portfolio total return: `(latest_index - 100)%`
- SPY total return: `(latest_spy_index - 100)%`
- Alpha: `portfolio_return - spy_return` (simple arithmetic alpha for display purposes)

### Backend Computation

```
GET /api/weekly/return-index?mode=AYTD|Max

Response:
{
  mode: "AYTD" | "Max",
  base_date: string,           // ISO date
  series: [
    {
      date: string,            // Label for X-axis (e.g., "Sep" or "2024-09")
      portfolio_index: number, // Rebased to 100
      benchmark_index: number  // Rebased to 100
    }
  ],
  portfolio_return_pct: number, // Total return since base
  benchmark_return_pct: number, // Total return since base
  alpha_pct: number             // Arithmetic difference
}
```

### Database Tables Involved

- `portfolio_snapshots` (date, nav) — for portfolio index
- `benchmark_snapshots` (date, close_price, ticker) — for SPY index
- `portfolio_settings` (aytd_start_date, inception_date, benchmark_ticker)

---

## 1.3 Top Alerts Preview

**Visual**: Compact list of the top 5 most urgent alerts, pulled from the Alerts & Attention engine (Module 5). Shows a truncated message, category label, severity color, and timestamp. Includes a "View all →" link that navigates to the Alerts tab.

### Data Requirements

This section is a direct consumer of the Module 5 alert engine output. It does not have its own logic — it simply queries the top 5 alerts sorted by severity (high first, then med), then by recency.

### Backend Computation

```
GET /api/alerts/top?limit=5

Response:
{
  alerts: [
    {
      id: string,
      category: "Position Size" | "Factor Breach" | "Drawdown" | "Correlation" | "Earnings" | "Macro",
      severity: "high" | "med" | "low" | "info",
      message: string,
      ticker: string | null,
      timestamp: string,
      icon: string
    }
  ],
  total_high: number,  // Count of high-severity alerts (shown in subtitle)
  total_count: number  // Total alert count
}
```

See [Module 5: Alerts & Attention](./05-ALERTS-ATTENTION.md) for the full alert generation logic.

---

## 1.4 Portfolio Heatmap (Treemap)

**Visual**: A hierarchical treemap where each rectangle represents a position. Rectangles are grouped by Sector, then by Industry, then sized by portfolio weight, and colored by performance.

**Toggle**: `Daily` / `Weekly` — switches the color encoding between 1-day % change and 5-day % change.

### Layout Logic

The treemap uses a nested proportional-area layout:

1. **Level 1 — Sector**: Each GICS sector gets a horizontal slice proportional to its total weight in the portfolio. Sectors are sorted by weight descending (largest sector on the left).
2. **Level 2 — Industry**: Within each sector slice, positions are grouped by GICS sub-industry.
3. **Level 3 — Ticker**: Each individual position is a colored rectangle. Size is proportional to its weight within the sector.

**Color Scale** (performance-based):

| Performance Range | Color | Hex |
|-------------------|-------|-----|
| ≥ +3% | Dark green | `#065F46` |
| +1.5% to +3% | Green | `#0A7B4F` |
| +0.5% to +1.5% | Light green | `#34D399` |
| −0.5% to +0.5% | Gray (neutral) | `#94A3B8` |
| −1.5% to −0.5% | Light red | `#F87171` |
| −3% to −1.5% | Red | `#C8220D` |
| ≤ −3% | Dark red | `#7F1D1D` |

**Tooltip** (on hover): `{Ticker} | {Industry} | Weight: {X}% | {Day/Week}: {±Y}%`

### Data Requirements

For every open position, the treemap needs:
- `ticker` — Display label
- `sector` — GICS sector for Level 1 grouping
- `industry` — GICS sub-industry for Level 2 grouping
- `weight` — Current portfolio weight (position market value / NAV * 100)
- `day_change_pct` — 1-day percentage price change
- `week_change_pct` — 5-day percentage price change

**Weight computation**: `weight = (shares * current_price) / NAV * 100`
**Day change**: `(close_today - close_yesterday) / close_yesterday * 100`
**Week change**: `(close_today - close_5_days_ago) / close_5_days_ago * 100`

### Backend Computation

```
GET /api/weekly/treemap

Response:
{
  positions: [
    {
      ticker: string,
      sector: string,           // GICS sector
      industry: string,         // GICS sub-industry
      weight: number,           // Portfolio weight %
      day_change_pct: number,   // 1-day % change
      week_change_pct: number   // 5-day % change
    }
  ]
}
```

### Database Tables Involved

- `positions` (ticker, shares, current_price, sector, industry) — for live weights
- `securities` (sector, industry) — GICS classification reference
- Market data provider — for daily/weekly price changes
- `portfolio_snapshots` (nav) — for weight denominator

---

## 1.5 Top 10 / Bottom 10 Movers

**Visual**: Two side-by-side panels. The left shows the 10 positions with the largest positive weekly percentage change. The right shows the 10 with the largest negative weekly change. Each row displays: rank number, ticker, industry, portfolio weight, and weekly % change.

### Purpose

With 247 positions, the middle 227 are noise during a weekly review. The tails — the biggest winners and biggest losers — are where the portfolio manager's attention should go. These lists answer: "What moved the most this week, and how much do I have at risk in each?"

### Data Requirements

This uses the same dataset as the treemap (`week_change_pct` per position), simply sorted:

- **Top 10**: `ORDER BY week_change_pct DESC LIMIT 10`
- **Bottom 10**: `ORDER BY week_change_pct ASC LIMIT 10`

Each row needs: `ticker`, `industry`, `weight`, `week_change_pct`.

### Backend Computation

```
GET /api/weekly/movers

Response:
{
  top: [
    { ticker: string, industry: string, weight: number, week_change_pct: number }
  ],  // 10 items, sorted by week_change_pct descending
  bottom: [
    { ticker: string, industry: string, weight: number, week_change_pct: number }
  ]   // 10 items, sorted by week_change_pct ascending
}
```

### Database Tables Involved

- Same as treemap: `positions`, `securities`, market data, `portfolio_snapshots`

---

## Frontend State

| State Variable | Type | Default | Controls |
|----------------|------|---------|----------|
| `curveMode` | `"AYTD" \| "Max"` | `"AYTD"` | Return index chart toggle |
| `heatMode` | `"day" \| "week"` | `"week"` | Treemap color encoding toggle |

---

## Data Refresh Strategy

| Data Point | Refresh Frequency | Trigger |
|------------|-------------------|---------|
| KPI strip | On page load + every 5 min during market hours | Timer / tab focus |
| Return index chart | On page load | Tab switch |
| Treemap | On page load + on toggle change | Toggle or refresh |
| Movers | On page load | Tab switch |
| Alerts preview | On page load + every 5 min | Timer |
