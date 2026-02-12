# Module 3: Construction

## Purpose

Construction is the portfolio manager's structural workshop. It answers: "Is my portfolio shaped the way I want it to be, and what should I change?" This tab is used for rebalancing decisions, allocation analysis, and pre-trade impact assessment.

---

## 3.1 Allocation Views

**Visual**: Full-width panel divided into two columns — Sector Drift (left) and Factor Drift + Cash Utilization (right).

### 3.1.1 Sector Drift

A table showing every GICS sector with its current portfolio weight, benchmark (SPY) target weight, and the drift between them. Each row includes a horizontal bar visualization.

| Column | Description | Source |
|--------|-------------|--------|
| Sector | GICS sector name | `securities.sector` |
| Weight Bar | Visual bar showing portfolio weight vs benchmark marker | Computed |
| Current % | Portfolio weight | `SUM(position_value) / NAV * 100` grouped by sector |
| Target % | Benchmark weight | `benchmark_weights.weight` for SPY |
| Drift | `Current - Target` | Computed, color-coded: green (|drift| < 1.5%), amber (1.5–3%), red (> 3%) |

**Computation**:
- Current sector weight: For each sector, `SUM(shares * current_price for all positions in sector) / NAV * 100`.
- Target weight: From `benchmark_weights` table, which stores SPY sector allocations (updated monthly).
- Drift: `current_weight - target_weight`. Positive = overweight, negative = underweight.

### 3.1.2 Factor Drift

A table showing portfolio-level factor exposures vs target exposures.

| Factor | Target (σ) | Current (σ) | Drift (σ) |
|--------|-----------|-------------|-----------|
| Momentum | +0.4 | +0.6 | +0.2 |
| Quality | +0.6 | +0.8 | +0.2 |
| Value | 0.0 | −0.3 | −0.3 |
| Size | 0.0 | −0.2 | −0.2 |
| Volatility | −0.2 | −0.4 | −0.2 |

**Computation**:
- Current factor exposure: Weighted average of per-security factor loadings. `portfolio_exposure_f = SUM(weight_i * loading_i_f)` for factor `f`.
- Target exposure: Stored in `portfolio_settings` or a dedicated `factor_targets` table.
- Drift: `current - target`, expressed in standard deviations. Color-coded: green (|drift| < 0.3σ), amber (> 0.3σ).
- Factor loadings per security come from a monthly-updated external source (AQR, MSCI Barra, or similar).

### 3.1.3 Cash Utilization

A compact card showing:
- **Available cash**: Dollar amount and percentage of NAV.
- **Invested percentage**: Visual progress bar.
- **Target**: From `portfolio_settings.cash_target_pct` (default 4%).

**Computation**: `invested_pct = (NAV - cash) / NAV * 100`.

### Backend Computation

```
GET /api/construction/allocation

Response:
{
  sectors: [
    {
      name: string,
      current_weight: number,  // Portfolio %
      target_weight: number,   // Benchmark %
      drift: number,           // Current - target
      position_count: number,
      color: string            // Hex for sector identity
    }
  ],
  factors: [
    {
      name: string,            // "Momentum", "Quality", etc.
      current_sigma: number,   // Current exposure in σ
      target_sigma: number,    // Target exposure in σ
      drift_sigma: number      // Current - target
    }
  ],
  cash: {
    amount: number,            // Dollar value
    pct_of_nav: number,        // Percentage
    invested_pct: number,      // (NAV - cash) / NAV * 100
    target_pct: number         // From settings
  }
}
```

### Database Tables Involved

- `positions` (ticker, shares, current_price, sector) — for sector weights
- `securities` (sector) — for GICS classification
- `benchmark_weights` (sector, weight) — for target allocation
- `factor_exposures` (ticker, momentum, quality, value, size, volatility) — per-security factor loadings
- `portfolio_settings` (cash_target_pct, factor targets)

---

## 3.2 What-If Staging Area

**Visual**: A trade entry form (left) and a radar chart with projected impact (right). The form allows the user to stage hypothetical trades and immediately see their effect on portfolio beta and sector weights without executing anything.

### Trade Entry

Each trade row has three fields:
- **Action**: `Buy` or `Sell` dropdown.
- **Ticker**: Text input (uppercase).
- **Amount**: Dollar amount.

The user can add multiple rows by clicking "+ Add trade". Each row can be removed individually.

**Example scenario**: "Buy $5,000 of NVDA financed by selling $5,000 of SPY."

### Projected Impact Computation

For each staged trade, the system recalculates:

**Portfolio Beta Change**:
- Look up the ticker's sector.
- Apply a sector-level beta assumption (or the security's individual beta if available).
- `delta_beta = sign * (amount / NAV) * security_beta`
- `new_portfolio_beta = current_beta + SUM(delta_beta for all staged trades)`

**Sector Weight Change**:
- `delta_weight = sign * (amount / NAV) * 100` allocated to the security's sector.
- Display shows each affected sector with its weight delta.

**Sector beta assumptions** (defaults, overridden by per-security data when available):

| Sector | Default β |
|--------|-----------|
| Technology | 1.15 |
| Healthcare | 0.82 |
| Financials | 1.08 |
| Energy | 1.20 |
| Consumer Disc. | 1.10 |
| Industrials | 1.05 |
| Comm. Services | 1.00 |
| Materials | 1.10 |
| Utilities | 0.55 |
| Cons. Staples | 0.65 |
| Real Estate | 0.75 |

### Radar Chart — Factor Shape

A 5-axis spider/radar chart comparing the portfolio's current factor profile with the new position's factor profile.

**Axes**: Momentum, Quality, Value, Size, Volatility (each in σ units, range −1 to +1).

- **Portfolio line** (solid blue): Current portfolio-level factor exposures from `factor_exposures` table.
- **Position line** (dashed purple): The first staged ticker's per-security factor loadings.

This allows the PM to visually assess whether the new trade diversifies or concentrates factor exposure.

### Backend Computation

```
POST /api/construction/what-if

Request Body:
{
  trades: [
    { action: "Buy" | "Sell", ticker: string, amount: number }
  ]
}

Response:
{
  current_beta: number,
  projected_beta: number,
  delta_beta: number,
  sector_deltas: [
    { sector: string, delta_weight: number }
  ],
  radar: {
    portfolio: { momentum: number, quality: number, value: number, size: number, volatility: number },
    position: { momentum: number, quality: number, value: number, size: number, volatility: number }
  }
}
```

### Database Tables Involved

- `positions` — for current weights (to compute beta contribution)
- `securities` (sector, beta, factor_loadings) — for lookup of staged tickers
- `portfolio_settings` — for current portfolio beta
- `factor_exposures` — for portfolio-level factor profile and per-security loadings

---

## 3.3 Diversification Metrics

**Visual**: 6-card grid showing quantitative diversification measures.

| Metric | Value | Interpretation |
|--------|-------|---------------|
| HHI (Herfindahl-Hirschman Index) | 342 | Sum of squared weights × 10,000. Lower = more diversified. Below 500 = well diversified. |
| Effective Positions | 29.2 | `1 / HHI_raw` (where HHI_raw = sum of squared weight fractions). The "effective number" of equal-weight positions. |
| Sector Entropy | 0.91 | Shannon entropy of sector weights, normalized to [0,1]. Higher = more evenly distributed. |
| Avg Correlation | 0.38 | Average pairwise correlation among all positions. Lower = better diversification. |
| Gini Coefficient | 0.64 | Inequality of position weights. 0 = perfectly equal, 1 = maximally concentrated. |
| Active Share | 72% | `0.5 * SUM(|portfolio_weight_i - benchmark_weight_i|)`. Measures divergence from benchmark. |

### Computation Details

**HHI**: `SUM(w_i^2) * 10000` where `w_i` = weight of position `i` as a decimal (e.g., 0.042 for 4.2%).
**Effective Positions**: `1 / SUM(w_i^2)`.
**Sector Entropy**: `H = -SUM(s_j * ln(s_j)) / ln(N_sectors)` where `s_j` = sector weight fraction, normalized by `ln(N)` to scale to [0,1].
**Avg Correlation**: Mean of upper triangle of position-level correlation matrix.
**Gini**: Sort weights ascending, compute `G = (2 * SUM(i * w_sorted_i)) / (n * SUM(w_i)) - (n + 1) / n`.
**Active Share**: Requires benchmark constituent weights; computed as `0.5 * SUM(|w_portfolio_i - w_benchmark_i|)` across all securities in either portfolio or benchmark.

### Backend Computation

```
GET /api/construction/diversification

Response:
{
  hhi: number,
  effective_positions: number,
  sector_entropy: number,
  avg_correlation: number,
  gini: number,
  active_share: number
}
```

---

## 3.4 Trim & Add Candidates

**Visual**: Two small panels side by side. **Trim** shows positions to reduce (red-accented). **Add** shows opportunities to increase (green-accented).

### Trim Logic (Rule-Based)

A position appears in the Trim list if any of the following conditions are met:
1. **Approaching position cap**: `weight >= max_position_weight * 0.80` (e.g., ≥4.0% if cap is 5%).
2. **Large unrealized gain**: `pnl_pct >= 30%` — consider locking in profits.
3. **Sector overweight**: The position's sector is overweight vs benchmark by more than `max_sector_overweight`.

Display: Ticker, reason, suggested trim amount (enough to bring back to a target weight).

### Add Logic (Rule-Based)

A position or sector appears in the Add list if:
1. **Sector underweight**: Sector is underweight vs benchmark by more than `max_sector_overweight`.
2. **Watchlist candidate with high score**: Security on the watchlist with composite score ≥ 75 (if watchlist system is implemented).
3. **Cash above target**: `cash_pct > cash_target_pct * 1.5` — surplus cash to deploy.

### Backend Computation

```
GET /api/construction/candidates

Response:
{
  trim: [
    { ticker: string, reason: string, suggested_action: string }
  ],
  add: [
    { label: string, reason: string, suggested_action: string }
  ]
}
```

---

## 3.5 All Positions Table

**Visual**: Full-width scrollable table showing every open position with filtering and sorting. This table was moved here from the Weekly Review module — the Weekly Review focuses on high-level patterns (treemap, movers), while Construction is where the PM drills into individual holdings.

### Columns

| Column | Key | Sortable | Description |
|--------|-----|----------|-------------|
| Ticker | `ticker` | Yes | Symbol with monospace font |
| Name | — | No | Company name |
| Sector | `sector` | Yes | GICS sector |
| Industry | `industry` | Yes | GICS sub-industry |
| Cap | `cap` | Yes | Market cap category: Large, Mid, Small (color-coded badges) |
| Strategy | `strategy_name` | Yes | Parent strategy name (links to Module 6 detail view). Shows "—" if unassigned. |
| Weight | `weight` | Yes | Portfolio weight % |
| Price | `price` | Yes | Current market price |
| Cost | `cost` | Yes | Average cost basis |
| P&L | `pnl` | Yes | Unrealized P&L % (`(price - cost) / cost * 100`) |
| Day | `dayChg` | Yes | 1-day % price change |
| Days | `days` | Yes | Days held (`today - entry_date`) |

**Note**: The "Thesis" column from v3 has been removed. Industry column was added after Sector. Strategy column links each position to its parent strategy (see Module 6).

### Filters

| Filter | Type | Options | Behavior |
|--------|------|---------|----------|
| Search | Text input | — | Filters by ticker or name (case-insensitive substring match) |
| Sector | Dropdown | All 11 GICS sectors | Exact match on sector |
| Cap | Dropdown | Large, Mid, Small | Exact match on market cap category |
| P&L | Dropdown | Winners, Losers | Filters to `pnl > 0` or `pnl < 0` |

### Sorting

Click any sortable column header to sort ascending/descending. Active sort column is highlighted in blue with a directional arrow (▼ / ▲). Default sort: `weight DESC`.

### Backend Computation

```
GET /api/construction/positions?search=&sector=&cap=&pnl=&strategy=&sort=weight&dir=desc

Response:
{
  positions: [
    {
      ticker: string,
      name: string,
      sector: string,
      industry: string,
      cap: "Large" | "Mid" | "Small",
      strategy_id: string | null,
      strategy_name: string | null,
      weight: number,
      price: number,
      cost: number,
      pnl_pct: number,
      day_change_pct: number,
      days_held: number
    }
  ],
  total_count: number
}
```

### Database Tables Involved

- `positions` (ticker, shares, entry_date, cost_basis, status, strategy_id)
- `securities` (name, sector, industry, market_cap_category)
- `strategies` (strategy_id, name) — for strategy name display
- Market data — for current price and day change
- `portfolio_snapshots` (nav) — for weight denominator

---

## Frontend State

| State Variable | Type | Default | Controls |
|----------------|------|---------|----------|
| `search` | `string` | `""` | Position search filter |
| `sectorFilter` | `string` | `""` | Sector dropdown |
| `capFilter` | `string` | `""` | Cap dropdown |
| `pnlFilter` | `string` | `""` | Winners/losers dropdown |
| `sortKey` | `string` | `"weight"` | Active sort column |
| `sortDir` | `"asc" \| "desc"` | `"desc"` | Sort direction |
| `whatIf` | `Array<{ticker, action, amount}>` | `[{ticker:"", action:"Buy", amount:"5000"}]` | Staged trades |
