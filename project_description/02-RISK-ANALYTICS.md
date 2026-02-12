# Module 2: Risk Analytics

## Purpose

Risk Analytics is the portfolio manager's risk control center. It answers: "What is my exposure to loss, where are the concentration risks, and how are my risk metrics trending?" This tab is used for ongoing risk monitoring, not pre-trade analysis.

---

## 2.1 Risk Summary Strip

**Visual**: Six metric cards in a horizontal row.

| Card | Label | Value Example | Sub-value | Color |
|------|-------|--------------|-----------|-------|
| 1 | VaR (95%) | `−$32.8K` | `Daily` | Red |
| 2 | CVaR | `−$48.2K` | `Exp. shortfall` | Red |
| 3 | Max DD | `−8.3%` | `−$85.1K` | Red |
| 4 | Vol | `14.8%` | `Ann. σ` | Neutral |
| 5 | Beta | `0.91` | `α: +3.2%` | Neutral |
| 6 | Track. Err | `6.8%` | `vs S&P` | Neutral |

### Data Requirements and Computation

**VaR (Value at Risk) — 95% confidence, 1-day horizon**:
- Method: Historical simulation using the most recent 252 trading days of daily portfolio returns.
- Computation: Sort daily returns ascending. VaR at 95% = the return at the 5th percentile (i.e., the 13th-worst day out of 252).
- Dollar VaR: `VaR_pct * NAV`.
- Source: `portfolio_snapshots` daily returns. Return = `(NAV_t - NAV_t-1) / NAV_t-1`.

**CVaR (Conditional VaR / Expected Shortfall)**:
- Formula: Average of all daily returns that fall below the VaR threshold.
- Dollar CVaR: `CVaR_pct * NAV`.

**Max Drawdown**:
- Formula: Largest peak-to-trough decline over the trailing 1-year period.
- Computation: Track running maximum of NAV. Drawdown at each point = `(NAV_t - running_max) / running_max`. Max DD = minimum of this series.
- Dollar value: `MaxDD_pct * peak_NAV`.

**Annualized Volatility**:
- Formula: `StdDev(daily_returns) * sqrt(252)` over trailing 1 year.

**Beta**:
- Formula: `Cov(portfolio_returns, benchmark_returns) / Var(benchmark_returns)` over trailing 1 year.
- Benchmark: SPY daily returns from `benchmark_snapshots`.

**Alpha**:
- Formula: `annualized_portfolio_return - (risk_free_rate + beta * (annualized_benchmark_return - risk_free_rate))`
- Simplified display version: `annualized_portfolio_return - beta * annualized_benchmark_return`.

**Tracking Error**:
- Formula: `StdDev(portfolio_return - benchmark_return) * sqrt(252)` over trailing 1 year.

### Backend Computation

```
GET /api/risk/summary

Response:
{
  var_95_pct: number,           // e.g., -3.2 (percent)
  var_95_dollar: number,        // e.g., -32800
  cvar_95_pct: number,          // e.g., -4.8
  cvar_95_dollar: number,       // e.g., -48200
  max_drawdown_pct: number,     // e.g., -8.3
  max_drawdown_dollar: number,  // e.g., -85100
  volatility_ann: number,       // e.g., 14.8
  beta: number,                 // e.g., 0.91
  alpha: number,                // e.g., 3.2
  tracking_error: number        // e.g., 6.8
}
```

### Database Tables Involved

- `portfolio_snapshots` (date, nav) — daily returns for all risk computations
- `benchmark_snapshots` (date, close_price) — SPY returns for beta, alpha, tracking error
- `risk_metrics` (cached computations, updated nightly)

---

## 2.2 Return Distribution Chart

**Visual**: Bar chart (histogram) of daily portfolio returns over the trailing 1 year. X-axis = return bins (e.g., −6% to +6% in 0.35% increments). Y-axis = frequency count. Color coding distinguishes normal returns, VaR tail, and CVaR tail.

| Region | Color | Opacity | Description |
|--------|-------|---------|-------------|
| Normal returns | Blue (`#1D4ED8`) | 0.20 | Returns above VaR threshold |
| VaR tail (5%) | Red (`#C8220D`) | 0.45 | Returns between VaR and CVaR |
| CVaR tail | Purple (`#6B21A8`) | 0.55 | Returns below CVaR threshold |

**Reference lines**: Vertical dashed lines at VaR (−3.2%) and CVaR (−4.5%).

### Data Requirements

- Input: Array of 252 daily portfolio returns (trailing 1 year).
- Processing: Bin returns into ~40 equally-spaced bins. Count frequency per bin. Tag each bin with `isVaR` (below VaR threshold) and `isCVaR` (below CVaR threshold).

### Backend Computation

```
GET /api/risk/return-distribution

Response:
{
  bins: [
    {
      return_midpoint: number,  // e.g., -3.2 (center of bin, in percent)
      frequency: number,        // Count of days in this bin
      is_var_tail: boolean,     // true if bin <= VaR threshold
      is_cvar_tail: boolean     // true if bin <= CVaR threshold
    }
  ],
  var_threshold: number,        // e.g., -3.2
  cvar_threshold: number        // e.g., -4.5
}
```

---

## 2.3 Drawdown History Chart

**Visual**: Area chart (filled downward) showing peak-to-trough drawdown over time. X-axis = months. Y-axis = drawdown percentage (always ≤ 0). A horizontal dashed reference line marks the maximum drawdown.

### Data Requirements

- Input: Daily `portfolio_snapshots.nav` for trailing 8–12 months.
- Computation:
  1. Compute `running_max = MAX(nav) up to date d`.
  2. Compute `drawdown_d = (nav_d - running_max) / running_max * 100`.
  3. Aggregate to monthly or weekly granularity for chart display.

### Backend Computation

```
GET /api/risk/drawdown

Response:
{
  series: [
    { date: string, drawdown_pct: number }  // Monthly aggregated
  ],
  max_drawdown_pct: number,     // For reference line
  max_drawdown_date: string     // When max DD occurred
}
```

---

## 2.4 Correlation Matrix

**Visual**: 8×8 color-coded grid. Toggleable between two views: **Top Positions** (top 8 by weight) and **Sectors** (8 sector groupings). Diagonal cells show "—". Off-diagonal cells show correlation coefficients with semantic coloring.

**Toggle**: `Positions` / `Sectors`

**Color scale**:

| Correlation Range | Color | Meaning |
|-------------------|-------|---------|
| ≥ 0.70 | Red (`#C8220D`) | High positive — concentration risk |
| 0.40 – 0.70 | Orange (`#C2410C`) | Moderate positive |
| 0.10 – 0.40 | Amber (`#A85D00`) | Low positive |
| −0.10 – 0.10 | Gray (`#8B99AD`) | Negligible |
| < −0.10 | Cyan (`#0E7490`) | Negative — diversification benefit |

### Data Requirements

**Position-level correlation (Positions view)**:
- Select top 8 positions by portfolio weight.
- Compute 90-day rolling pairwise Pearson correlation using daily returns.
- Returns: `(price_t - price_t-1) / price_t-1` for each security.
- Output: 8×8 symmetric matrix.

**Sector-level correlation (Sectors view)**:
- Compute a daily sector-level return as the weighted average return of all positions in each sector.
- Compute 90-day rolling pairwise correlation between sector return series.
- Output: 8×8 symmetric matrix (or up to 11×11 for all GICS sectors).

### Backend Computation

```
GET /api/risk/correlation?view=position|sector

Response:
{
  labels: string[],             // e.g., ["NVDA","MSFT",...] or ["Tech","Health",...]
  matrix: number[][],           // Symmetric correlation matrix
  window_days: number,          // e.g., 90
  high_pairs: [                 // Pairs above correlation_flag threshold
    { pair: [string, string], correlation: number }
  ]
}
```

### Database Tables Involved

- `position_snapshots` (date, ticker, market_value) — for daily position returns
- Market data — for daily prices per ticker
- `securities` (sector) — for sector grouping
- `portfolio_settings` (correlation_flag) — threshold for flagging

---

## 2.5 Rolling Metrics Table

**Visual**: Table with 4 rows (time windows) and 6 columns showing how risk metrics evolve over different lookback periods.

| Window | Sharpe | Sortino | Volatility | Beta | Max DD |
|--------|--------|---------|-----------|------|--------|
| 30d | 1.68 | 2.12 | 12.4% | 0.88 | −2.1% |
| 90d | 1.42 | 1.87 | 14.8% | 0.91 | −5.6% |
| 180d | 1.31 | 1.64 | 15.9% | 0.93 | −8.3% |
| 1Y | 1.24 | 1.52 | 16.2% | 0.94 | −8.3% |

### Data Requirements

For each window (30d, 90d, 180d, 252d):

- **Sharpe**: `(annualized_return - risk_free_rate) / annualized_volatility`
- **Sortino**: `(annualized_return - risk_free_rate) / downside_deviation`. Downside deviation uses only negative returns.
- **Volatility**: `StdDev(daily_returns) * sqrt(252)`
- **Beta**: `Cov(port, bench) / Var(bench)`
- **Max DD**: Largest peak-to-trough in the window.

Green highlighting: Sharpe ≥ 1.5, Sortino ≥ 2.0 (indicates strong risk-adjusted performance).

### Backend Computation

```
GET /api/risk/rolling

Response:
{
  windows: [
    {
      period: string,        // "30d", "90d", "180d", "1Y"
      sharpe: number,
      sortino: number,
      volatility: number,    // Annualized %
      beta: number,
      max_drawdown: number   // %
    }
  ]
}
```

---

## 2.6 Factor Risk Decomposition

**Visual**: Horizontal bar chart showing what percentage of total portfolio variance is attributable to each risk factor.

| Factor | % of Variance | Color |
|--------|---------------|-------|
| Market (β) | 62% | Blue |
| Sector Selection | 14% | Purple |
| Momentum | 8% | Green |
| Size | 5% | Amber |
| Value | 4% | Cyan |
| Idiosyncratic | 7% | Gray |

### Data Requirements

Factor risk decomposition requires a multi-factor risk model:

1. Regress portfolio daily returns against factor returns (market, sector, momentum, size, value).
2. The R² attributable to each factor gives its share of explained variance.
3. Idiosyncratic = `1 - sum(all_factor_R²)`.

Factor return sources:
- **Market**: SPY or total market return.
- **Sector**: Long-short sector factor returns (or decompose by sector tilts).
- **Momentum, Size, Value**: Fama-French or AQR factor return series.

### Backend Computation

```
GET /api/risk/factor-decomposition

Response:
{
  factors: [
    { name: string, variance_pct: number }
  ]
}
```

### Database Tables Involved

- `factor_exposures` (portfolio-level factor regression output, updated nightly)
- External factor return data (Fama-French, AQR, or custom)

---

## Frontend State

| State Variable | Type | Default | Controls |
|----------------|------|---------|----------|
| `corrView` | `"position" \| "sector"` | `"position"` | Correlation matrix toggle |
