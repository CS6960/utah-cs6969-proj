# Meridian — Equity Portfolio Management System (v4)

## System Purpose

Meridian is a portfolio management dashboard for an active equity portfolio of approximately $1M across 200–300 open positions. The portfolio is managed by **multiple manager teams** deploying three strategy types: fundamental (single-position), systematic (multi-position baskets with periodic reconstruction), and macroeconomic (multi-position baskets driven by macro themes). The system serves the CIO/lead PM with six operational workflows: weekly operational review, risk monitoring, portfolio construction and rebalancing, post-trade analysis, proactive alerting, and manager/strategy performance attribution.

## Architecture Summary

The frontend is a single-page React application with six tabbed modules. Each module consumes data from a backend API that queries a relational database and performs computed analytics.

| Module | Tab Label | Primary Use Case |
|--------|-----------|-----------------|
| 1 | Weekly Review | Operational heartbeat — "how am I doing?" |
| 2 | Risk Analytics | Risk monitoring — "what could go wrong?" |
| 3 | Construction | Portfolio structure — "what should I change?" |
| 4 | Closed Positions | Post-trade learning — "what worked and what didn't?" |
| 5 | Alerts & Attention | Proactive intelligence — "what needs my attention now?" |
| 6 | Manager Performance | Team and strategy attribution — "who is generating alpha?" |

## Global Configuration

The system uses several user-configurable parameters stored in a `portfolio_settings` table:

| Setting | Default | Description |
|---------|---------|-------------|
| `aytd_start_date` | `2025-09-01` | Reset date for AYTD (Annualized Year-to-Date) calculations |
| `inception_date` | `2024-09-01` | Fund inception date for max-horizon return calculations |
| `benchmark_ticker` | `SPY` | Benchmark ETF for comparative analytics |
| `max_position_weight` | `5.0%` | Hard cap on any single position |
| `max_sector_overweight` | `5.0%` | Max deviation from benchmark sector weight |
| `factor_ceiling` | `1.0σ` | Max factor exposure deviation |
| `drawdown_trigger` | `-5.0%` | Sector or position drawdown that triggers review |
| `correlation_flag` | `0.75` | Pairwise correlation threshold for alerts |
| `stop_loss_default` | `-8.0%` | Default stop loss from cost basis |
| `max_positions` | `300` | Position count capacity |
| `cash_target_pct` | `4.0%` | Target cash allocation |

## Database Schema Overview

The system requires the following core tables:

### Reference Data
- `securities` — Ticker, name, sector (GICS), industry (GICS sub-industry), market cap category, and factor loadings
- `benchmark_weights` — Current benchmark (SPY) sector and position weights, updated monthly
- `earnings_calendar` — Upcoming earnings dates for held securities
- `macro_events` — Fed meetings, CPI releases, and other macro catalysts

### Manager & Strategy Data
- `manager_teams` — Organizational units responsible for groups of strategies (team_id, name, description, lead_manager, inception_date, is_active)
- `strategies` — Named investment initiatives owned by a manager team (strategy_id, team_id FK, name, type [fundamental/systematic/macroeconomic], status [active/inactive], thesis, inception_date, closed_date, rebalance_frequency, benchmark_ticker)
- `strategy_reconstructions` — Log of reconstruction events within multi-position strategies (reconstruction_id, strategy_id FK, date, period_number, positions_added[], positions_removed[], note, prior_period_return_pct)
- `strategy_snapshots` — Daily time series of strategy-level market value, daily return, cumulative index, and realized P&L

### Portfolio Data
- `positions` — Current open positions with entry date, cost basis, shares, current market value, **`strategy_id` FK**, and **`reconstruction_period`**
- `closed_positions` — Historical closed trades with entry/exit dates, prices, P&L, hold duration, exit reason, **`strategy_id` FK**, and **`reconstruction_period`**
- `transactions` — Full trade log (buys, sells, dividends, corporate actions), with **`strategy_id` FK**

### Time Series
- `portfolio_snapshots` — Daily portfolio-level NAV, cash, position count, and return index value
- `position_snapshots` — Daily per-position market value and weight
- `benchmark_snapshots` — Daily benchmark index value (rebased to 100 at inception and AYTD start)

### Analytics (Computed, Cached)
- `risk_metrics` — Rolling VaR, CVaR, volatility, beta, alpha, Sharpe, Sortino, max drawdown, tracking error at multiple windows (30d, 90d, 180d, 1Y)
- `correlation_matrix` — Rolling 90-day pairwise correlations for top N positions and for sectors
- `return_distribution` — Binned daily return frequencies for the VaR histogram
- `factor_exposures` — Portfolio-level and position-level factor loadings (Momentum, Quality, Value, Size, Volatility)
- `drawdown_series` — Daily peak-to-trough drawdown time series

### Alerts
- `alert_rules` — Configurable alert rule definitions with thresholds
- `alert_instances` — Generated alert records with category, severity, message, ticker reference, and timestamp

## API Endpoint Summary

Each module has a corresponding API endpoint group. See individual module docs for detailed field specifications.

| Endpoint | Module | Description |
|----------|--------|-------------|
| `GET /api/weekly/kpi` | 1 | KPI strip values |
| `GET /api/weekly/return-index` | 1 | Rate of return index series |
| `GET /api/weekly/treemap` | 1 | Position heatmap data |
| `GET /api/weekly/movers` | 1 | Top/bottom 10 weekly movers |
| `GET /api/alerts/top?limit=5` | 1, 5 | Top alerts by severity |
| `GET /api/risk/summary` | 2 | VaR, CVaR, vol, beta, alpha, tracking error |
| `GET /api/risk/return-distribution` | 2 | Binned return histogram |
| `GET /api/risk/drawdown` | 2 | Drawdown time series |
| `GET /api/risk/correlation` | 2 | Correlation matrix (positions and sectors) |
| `GET /api/risk/rolling` | 2 | Rolling risk metrics at multiple windows |
| `GET /api/risk/factor-decomposition` | 2 | Factor risk attribution |
| `GET /api/construction/allocation` | 3 | Sector drift, factor drift, cash utilization |
| `GET /api/construction/what-if` | 3 | What-if trade impact calculation |
| `GET /api/construction/diversification` | 3 | HHI, effective positions, entropy, etc. |
| `GET /api/construction/candidates` | 3 | Trim and add recommendations |
| `GET /api/construction/positions` | 3 | Full position table with filters/sort |
| `GET /api/closed/summary` | 4 | Aggregate closed-position statistics |
| `GET /api/closed/trades` | 4 | Paginated trade log |
| `GET /api/closed/analytics` | 4 | Return distribution, hold-time scatter, exit analysis |
| `GET /api/alerts` | 5 | Full alert feed with category/severity filters |
| `GET /api/alerts/summary` | 5 | Severity counts and focus list |
| `GET /api/managers/summary` | 6 | Manager team summary metrics |
| `GET /api/managers/{team_id}/strategies` | 6 | Strategy list for a team |
| `GET /api/managers/strategies/{strategy_id}` | 6 | Strategy detail with positions, return index, reconstruction timeline |
| `GET /api/managers/comparison` | 6 | Cross-team comparison metrics and return overlay |
| `GET /api/managers/attribution` | 6 | Return attribution by team and by strategy type |

## External Data Dependencies

| Source | Data | Frequency | Purpose |
|--------|------|-----------|---------|
| Market data provider (e.g., Polygon, Alpha Vantage) | Real-time/EOD prices | Daily | Position valuation, return calculations |
| GICS classification | Sector and industry mapping | Quarterly | Treemap hierarchy, sector allocation |
| Factor data (e.g., AQR, Fama-French) | Factor loadings per security | Monthly | Factor exposure, radar chart, factor decomposition |
| Earnings calendar (e.g., Nasdaq) | Reporting dates | Weekly | Earnings alerts |
| Economic calendar | Fed meetings, CPI dates | Monthly | Macro event alerts |
| Benchmark holdings (SPY) | Sector and constituent weights | Monthly | Benchmark comparison, drift calculations |

## Module Documentation

Each module is documented in its own file with detailed specifications:

- [Module 1: Weekly Review](./01-WEEKLY-REVIEW.md)
- [Module 2: Risk Analytics](./02-RISK-ANALYTICS.md)
- [Module 3: Construction](./03-CONSTRUCTION.md)
- [Module 4: Closed Positions](./04-CLOSED-POSITIONS.md)
- [Module 5: Alerts & Attention](./05-ALERTS-ATTENTION.md)
- [Module 6: Manager Performance](./06-MANAGER-PERFORMANCE.md)
