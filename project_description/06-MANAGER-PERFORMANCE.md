# Module 6: Manager Performance

## Purpose

Manager Performance is the portfolio's attribution and accountability layer. It answers: "Which teams are generating returns, which strategies are working, and how does each manager's risk-adjusted performance compare?" This module exists because the portfolio is not run by one person making isolated stock picks — it is managed by **multiple teams** deploying **different strategy types**, and the CIO needs to evaluate each team's contribution independently.

---

## Conceptual Model

### The Three-Level Hierarchy

```
Portfolio ($1M, 247 positions)
  └─ Manager Team (e.g., "Alpha Equity", "Macro Rates", "Quant Momentum")
       └─ Strategy (e.g., "Semiconductor Cycle Q1-26", "Long Defensive Value")
            └─ Position(s) (e.g., NVDA, AVGO, AMAT)
```

Every open and closed position in the portfolio belongs to exactly one **strategy**, and every strategy belongs to exactly one **manager team**.

### Strategy Types

| Type | Typical Structure | Lifecycle | Example |
|------|-------------------|-----------|---------|
| **Fundamental** | Single position | Open → Close. One entry, one exit. No reconstruction. | "Long LLY on GLP-1 thesis" |
| **Systematic** | Multi-position basket | Opened as a basket → periodically **reconstructed** (positions added/removed) → eventually all positions closed and strategy marked inactive. | "Momentum Top Decile Q4-25" rebalanced quarterly |
| **Macroeconomic** | Multi-position basket | Same as systematic but driven by a macro thesis rather than quantitative signals. Reconstructions may be event-driven. | "Inflation Hedge — Energy + Commodities" adjusted after CPI prints |

### Strategy Lifecycle

A strategy moves through these states:

```
ACTIVE ──→ ACTIVE (reconstructed) ──→ ... ──→ INACTIVE
```

- **ACTIVE**: At least one open position. The strategy is live and contributing to portfolio P&L.
- **Reconstructed**: Some positions are closed and new positions are opened, but the strategy continues under the same identity. Each reconstruction is a dated event. The strategy's cumulative return spans all reconstruction periods.
- **INACTIVE**: All positions have been closed. The strategy is complete. It remains in the system for historical analysis but no longer contributes to live P&L.

### Reconstruction Events

A reconstruction is a rebalancing event within a strategy. It is not a new strategy — it is the same strategy evolving over time. Each reconstruction:

1. Closes some or all current positions in the strategy.
2. Opens new positions within the same strategy.
3. Is recorded with a date and an optional note (e.g., "Q1-26 rebalance: rotated out of XOM, added CVX").

**Frequency**: Typically quarterly for systematic, but configurable per strategy. Can be monthly, semi-annual, annual, or ad hoc for macroeconomic.

---

## 6.1 Manager Summary Strip

**Visual**: Three metric cards per manager team, displayed in a horizontal row. If there are 3 teams, the strip shows 3 groups. A dropdown allows selecting a single team or "All Teams."

### Per-Team Metrics

| Card | Label | Computation |
|------|-------|-------------|
| 1 | Allocated Capital | `SUM(current_market_value)` of all open positions belonging to the team |
| 2 | Total Return | Cumulative return across all active + inactive strategies, capital-weighted |
| 3 | Active Strategies | `COUNT(strategies WHERE status = 'active')` / total strategy count |

### All-Teams Overview Metrics

| Card | Label | Computation |
|------|-------|-------------|
| 1 | Teams | Total number of manager teams |
| 2 | Active Strategies | Count across all teams |
| 3 | Capital Deployed | `SUM(all open position values)` as % of NAV |

### Backend Computation

```
GET /api/managers/summary?team_id=all|{team_id}

Response:
{
  teams: [
    {
      team_id: string,
      team_name: string,
      allocated_capital: number,       // Dollar value of open positions
      allocated_pct: number,           // % of portfolio NAV
      total_return_pct: number,        // Capital-weighted cumulative return
      active_strategies: number,
      inactive_strategies: number,
      total_strategies: number,
      ytd_return_pct: number,
      sharpe: number,
      win_rate_pct: number             // % of closed strategies that were profitable
    }
  ]
}
```

---

## 6.2 Team Selector & Strategy Table

**Visual**: A dropdown or tab row to select a manager team. Below it, a table listing all strategies belonging to that team.

### Strategy Table Columns

| Column | Key | Description |
|--------|-----|-------------|
| Strategy Name | `name` | Descriptive name (e.g., "Momentum Top Decile Q4-25") |
| Type | `type` | `Fundamental` / `Systematic` / `Macroeconomic` badge |
| Status | `status` | `Active` (green dot) / `Inactive` (gray dot) |
| Positions | `position_count` | Current open position count. For fundamental = 0 or 1. For baskets = N. |
| Inception | `inception_date` | Strategy start date |
| Last Recon. | `last_reconstruction` | Date of last reconstruction (null for fundamental) |
| Recon. Count | `reconstruction_count` | Number of reconstructions to date |
| Invested | `invested_capital` | Current market value of open positions |
| Cumul. Return | `cumulative_return_pct` | Time-weighted return since inception across all reconstructions |
| AYTD Return | `aytd_return_pct` | Return since AYTD start date |
| Realized P&L | `realized_pnl` | Sum of closed-position P&L dollars within this strategy |
| Unrealized P&L | `unrealized_pnl` | Sum of open-position unrealized P&L |

**Sorting**: Default sort by `invested_capital DESC` (largest active strategies first). Inactive strategies sort below active ones.

**Filter**: A toggle to show `Active Only` / `All` / `Inactive Only`.

### Backend Computation

```
GET /api/managers/{team_id}/strategies?status=active|inactive|all&sort=invested_capital&dir=desc

Response:
{
  team: { team_id: string, team_name: string },
  strategies: [
    {
      strategy_id: string,
      name: string,
      type: "fundamental" | "systematic" | "macroeconomic",
      status: "active" | "inactive",
      position_count: number,
      inception_date: string,
      last_reconstruction_date: string | null,
      reconstruction_count: number,
      invested_capital: number,
      cumulative_return_pct: number,
      aytd_return_pct: number,
      realized_pnl: number,
      unrealized_pnl: number
    }
  ]
}
```

---

## 6.3 Strategy Detail View

When the user clicks a strategy row, a detail panel expands or a drill-down view opens showing the full history and current state of that strategy.

### 6.3.1 Strategy Header

| Field | Description |
|-------|-------------|
| Name | Strategy name |
| Team | Manager team name |
| Type | Fundamental / Systematic / Macroeconomic |
| Status | Active / Inactive |
| Inception | Start date |
| Thesis | Free-text description of the investment thesis (stored in `strategies.thesis`) |

### 6.3.2 Strategy KPI Strip

| Card | Label | Computation |
|------|-------|-------------|
| 1 | Cumulative Return | TWR since inception |
| 2 | AYTD Return | TWR since AYTD date |
| 3 | Realized P&L | Sum of closed positions' dollar P&L |
| 4 | Unrealized P&L | Sum of open positions' unrealized P&L |
| 5 | Reconstructions | Count of reconstruction events |
| 6 | Duration | Days from inception to today (or to final close) |

### 6.3.3 Return Chart

**Visual**: Line chart showing the strategy's cumulative return index (base 100 at inception) over time, with vertical dashed lines marking each reconstruction event.

**Computation**:
- Build a daily return series for the strategy by computing the weighted daily return of all positions belonging to the strategy on each day.
- On reconstruction days, the portfolio composition changes but the index is continuous (no reset).
- The return index = `100 * PRODUCT(1 + daily_return_t)` from inception to current.

Vertical markers at each reconstruction date let the PM see how performance changed after each rebalancing event.

### 6.3.4 Position History Table

A table showing every position that has ever been part of this strategy, across all reconstruction periods.

| Column | Description |
|--------|-------------|
| Ticker | Security symbol |
| Period | Which reconstruction period (e.g., "P1: Sep–Dec 2025", "P2: Jan–Mar 2026") |
| Entry Date | When the position was opened within this strategy |
| Exit Date | When closed (blank if still open) |
| Entry Price | Cost basis |
| Exit Price | Sale price (blank if open) |
| Return % | P&L percentage |
| P&L $ | Dollar P&L |
| Status | `Open` / `Closed` |

**Grouping**: Rows are visually grouped by reconstruction period with a period header row showing the period dates and aggregate return.

### 6.3.5 Reconstruction Timeline

**Visual**: A horizontal timeline or vertical list showing each reconstruction event.

| Field | Description |
|-------|-------------|
| Date | Reconstruction date |
| Period | "Period 1 → Period 2" |
| Positions Out | Tickers removed |
| Positions In | Tickers added |
| Note | Optional manager commentary |
| Period Return | Return of the prior period that just ended |

### Backend Computation

```
GET /api/managers/strategies/{strategy_id}

Response:
{
  strategy: {
    strategy_id: string,
    name: string,
    team_id: string,
    team_name: string,
    type: string,
    status: string,
    inception_date: string,
    thesis: string,
    cumulative_return_pct: number,
    aytd_return_pct: number,
    realized_pnl: number,
    unrealized_pnl: number,
    reconstruction_count: number,
    duration_days: number
  },
  return_index: [
    { date: string, index_value: number }
  ],
  reconstruction_events: [
    {
      event_id: string,
      date: string,
      period_label: string,
      positions_removed: string[],
      positions_added: string[],
      note: string | null,
      prior_period_return_pct: number
    }
  ],
  positions: [
    {
      ticker: string,
      period_label: string,
      entry_date: string,
      exit_date: string | null,
      entry_price: number,
      exit_price: number | null,
      return_pct: number | null,
      pnl_dollar: number | null,
      status: "open" | "closed"
    }
  ]
}
```

---

## 6.4 Team Comparison View

**Visual**: A comparison panel that shows all teams side-by-side on key metrics. Available when "All Teams" is selected.

### Comparison Table

| Metric | Team A | Team B | Team C |
|--------|--------|--------|--------|
| Capital Allocated | $420K | $310K | $245K |
| % of NAV | 41.0% | 30.3% | 23.9% |
| Cumulative Return | +14.2% | +8.7% | +18.4% |
| AYTD Return | +11.1% | +6.3% | +13.9% |
| Sharpe Ratio | 1.52 | 0.94 | 1.78 |
| Win Rate (strategies) | 72% | 58% | 80% |
| Active Strategies | 12 | 8 | 6 |
| Avg Strategy Duration | 142d | 98d | 210d |
| Realized P&L | +$38.2K | +$12.1K | +$29.8K |
| Unrealized P&L | +$21.4K | −$3.2K | +$18.6K |

### Team Return Overlay Chart

**Visual**: Line chart with one line per team, showing each team's return index (base 100 at inception or AYTD start), overlaid on the same axes. Allows visual comparison of who is generating alpha.

### Strategy Type Breakdown

**Visual**: For each team, a small bar or pie showing the mix of strategy types (fundamental vs systematic vs macroeconomic) by capital allocation.

### Backend Computation

```
GET /api/managers/comparison

Response:
{
  teams: [
    {
      team_id: string,
      team_name: string,
      capital: number,
      capital_pct: number,
      cumulative_return_pct: number,
      aytd_return_pct: number,
      sharpe: number,
      win_rate_pct: number,
      active_strategies: number,
      avg_duration_days: number,
      realized_pnl: number,
      unrealized_pnl: number,
      type_breakdown: {
        fundamental: { count: number, capital: number },
        systematic: { count: number, capital: number },
        macroeconomic: { count: number, capital: number }
      }
    }
  ],
  return_overlay: [
    {
      date: string,
      [team_id: string]: number  // index value per team
    }
  ]
}
```

---

## 6.5 Attribution Analysis

**Visual**: Panel showing how much of the total portfolio return is attributable to each team and each strategy type.

### Return Attribution Table

| Source | Weight | Return | Contribution |
|--------|--------|--------|-------------|
| Team Alpha Equity | 41.0% | +14.2% | +5.82% |
| Team Quant Systems | 30.3% | +8.7% | +2.64% |
| Team Macro Themes | 23.9% | +18.4% | +4.40% |
| Cash Drag | 4.7% | +0.2% | +0.01% |
| **Portfolio** | **100%** | — | **+12.87%** |

**Contribution formula**: `team_weight * team_return = contribution to portfolio return`.

### Strategy Type Attribution

Same structure but grouped by strategy type across all teams:

| Type | Weight | Return | Contribution |
|------|--------|--------|-------------|
| Fundamental | 48.2% | +12.1% | +5.83% |
| Systematic | 32.4% | +14.8% | +4.80% |
| Macroeconomic | 14.7% | +15.3% | +2.25% |

### Backend Computation

```
GET /api/managers/attribution?period=AYTD|YTD|Max

Response:
{
  period: string,
  by_team: [
    {
      team_id: string,
      team_name: string,
      weight_pct: number,
      return_pct: number,
      contribution_pct: number
    }
  ],
  by_strategy_type: [
    {
      type: string,
      weight_pct: number,
      return_pct: number,
      contribution_pct: number
    }
  ],
  cash_drag: {
    weight_pct: number,
    return_pct: number,
    contribution_pct: number
  },
  total_portfolio_return_pct: number
}
```

---

## Database Schema — New Tables

### `manager_teams`

The organizational unit responsible for a group of strategies.

| Column | Type | Description |
|--------|------|-------------|
| `team_id` | UUID, PK | Unique identifier |
| `name` | VARCHAR(100) | Team display name (e.g., "Alpha Equity") |
| `description` | TEXT | Team mandate and approach |
| `lead_manager` | VARCHAR(100) | Primary portfolio manager name |
| `inception_date` | DATE | When the team started managing capital |
| `is_active` | BOOLEAN | Whether the team is currently active |
| `created_at` | TIMESTAMP | Record creation time |

### `strategies`

A named investment initiative owned by a manager team. This is the core tracking unit.

| Column | Type | Description |
|--------|------|-------------|
| `strategy_id` | UUID, PK | Unique identifier |
| `team_id` | UUID, FK → `manager_teams` | Owning team |
| `name` | VARCHAR(200) | Descriptive name (e.g., "Momentum Top Decile Q4-25") |
| `type` | ENUM('fundamental','systematic','macroeconomic') | Strategy classification |
| `status` | ENUM('active','inactive') | Current lifecycle state |
| `thesis` | TEXT | Investment thesis / rationale |
| `inception_date` | DATE | When the strategy was first deployed |
| `closed_date` | DATE, nullable | When all positions were closed and strategy marked inactive |
| `rebalance_frequency` | ENUM('monthly','quarterly','semi_annual','annual','ad_hoc'), nullable | Expected reconstruction cadence (null for fundamental) |
| `benchmark_ticker` | VARCHAR(10), nullable | Strategy-specific benchmark if different from portfolio default |
| `created_at` | TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | Last modification time |

**Constraints**:
- For `type = 'fundamental'`: `rebalance_frequency` should be NULL (no reconstruction).
- For `status = 'inactive'`: `closed_date` must be set.

### `strategy_reconstructions`

A log of every reconstruction event within a strategy. Fundamental strategies will have zero rows here.

| Column | Type | Description |
|--------|------|-------------|
| `reconstruction_id` | UUID, PK | Unique identifier |
| `strategy_id` | UUID, FK → `strategies` | Parent strategy |
| `date` | DATE | Date of the reconstruction |
| `period_number` | INT | Sequential period number (1, 2, 3...) |
| `period_label` | VARCHAR(50) | Human-readable label (e.g., "P2: Jan–Mar 2026") |
| `positions_added` | TEXT[] | Array of tickers added in this reconstruction |
| `positions_removed` | TEXT[] | Array of tickers removed in this reconstruction |
| `note` | TEXT, nullable | Manager commentary on the reconstruction rationale |
| `prior_period_return_pct` | DECIMAL(8,4), nullable | Return of the period that just ended |
| `created_at` | TIMESTAMP | Record creation time |

### `strategy_snapshots`

Daily time series of strategy-level aggregated metrics, used for return index computation and team-level analytics.

| Column | Type | Description |
|--------|------|-------------|
| `snapshot_id` | UUID, PK | Unique identifier |
| `strategy_id` | UUID, FK → `strategies` | Parent strategy |
| `date` | DATE | Snapshot date |
| `market_value` | DECIMAL(14,2) | Sum of all open position market values in this strategy |
| `daily_return_pct` | DECIMAL(8,6) | Strategy-level daily return (weighted avg of position returns) |
| `cumulative_index` | DECIMAL(10,4) | Cumulative return index (base 100 at inception) |
| `realized_pnl_cumulative` | DECIMAL(14,2) | Cumulative realized P&L to date |

**Index**: Unique on `(strategy_id, date)`.

### Modifications to Existing Tables

#### `positions` — Add Columns

| New Column | Type | Description |
|------------|------|-------------|
| `strategy_id` | UUID, FK → `strategies`, nullable | Which strategy this position belongs to. Nullable for legacy positions not yet assigned. |
| `reconstruction_period` | INT, nullable | Which reconstruction period this position entered in (1, 2, 3...). NULL for fundamental strategies. |

#### `closed_positions` — Add Columns

| New Column | Type | Description |
|------------|------|-------------|
| `strategy_id` | UUID, FK → `strategies`, nullable | Which strategy this closed position belonged to. |
| `reconstruction_period` | INT, nullable | Which reconstruction period this position was part of. |

#### `transactions` — Add Column

| New Column | Type | Description |
|------------|------|-------------|
| `strategy_id` | UUID, FK → `strategies`, nullable | Strategy context for the transaction. |

---

## Return Computation Logic

### Strategy-Level Return

The strategy return is a **time-weighted return (TWR)** that spans all reconstruction events, ensuring continuity.

**Daily strategy return**:
```
strategy_return_t = SUM(weight_i_t * position_return_i_t)
    for all positions i that are open in the strategy on day t

where:
    weight_i_t = position_i_market_value_t / strategy_market_value_t
    position_return_i_t = (price_i_t - price_i_{t-1}) / price_i_{t-1}
```

**On reconstruction days**: Some positions close (capturing realized P&L) and new positions open. The strategy's market value changes. The return for that day reflects the combined effect of closing positions at their closing prices and opening new positions at their opening prices.

**Cumulative index**:
```
index_t = index_{t-1} * (1 + strategy_return_t)
index_inception = 100
```

### Team-Level Return

```
team_return_t = SUM(strategy_weight_j_t * strategy_return_j_t)
    for all active strategies j belonging to the team on day t

where:
    strategy_weight_j_t = strategy_market_value_j_t / team_market_value_t
```

### Strategy Sharpe Ratio

```
sharpe = (annualized_return - risk_free_rate) / annualized_volatility
    where:
        annualized_return = (latest_index / 100)^(252 / trading_days) - 1
        annualized_volatility = StdDev(daily_returns) * sqrt(252)
```

### Strategy Win Rate

Only applicable to completed (inactive) strategies:
```
win_rate = COUNT(inactive strategies with cumulative_return > 0) / COUNT(inactive strategies)
```

For active strategies, win rate is based on reconstruction periods: how many periods ended with positive returns.

---

## Frontend State

| State Variable | Type | Default | Controls |
|----------------|------|---------|----------|
| `selectedTeam` | `string` | `"all"` | Team selector dropdown |
| `strategyFilter` | `"active" \| "inactive" \| "all"` | `"active"` | Strategy status filter |
| `selectedStrategy` | `string \| null` | `null` | Clicked strategy for detail view |
| `attrPeriod` | `"AYTD" \| "YTD" \| "Max"` | `"AYTD"` | Attribution period toggle |

---

## Data Refresh Strategy

| Data Point | Refresh Frequency | Trigger |
|------------|-------------------|---------|
| Manager summary strip | On page load | Tab switch |
| Strategy table | On page load + team change | Team selector |
| Strategy detail | On click | Row click |
| Team comparison | On page load (when "All" selected) | Team selector |
| Attribution | On page load | Period toggle |
| Strategy snapshots | Nightly batch | EOD job computes daily returns and updates cumulative index |
