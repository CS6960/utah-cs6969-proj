# Module 4: Closed Positions

## Purpose

Closed Positions is the portfolio manager's post-trade learning system. It answers: "What was my realized performance, which strategies worked, and what patterns should I learn from?" This tab is used for periodic performance review and process improvement, not daily operations.

---

## 4.1 Summary Statistics Strip

**Visual**: Six metric cards showing aggregate performance of all closed trades.

| Card | Label | Value | Computation |
|------|-------|-------|-------------|
| 1 | Realized P&L | `$26,250` | `SUM(realized_pnl_dollar)` for all closed positions |
| 2 | Avg Return | `+5.6%` | `AVG(realized_pnl_pct)` across all closed trades |
| 3 | Win Rate | `58%` | `COUNT(pnl > 0) / COUNT(all) * 100`. Sub-value: `{wins}W / {losses}L` |
| 4 | Avg Win / Loss | `+22.2% / −14.1%` | `AVG(pnl WHERE pnl > 0)` and `AVG(pnl WHERE pnl <= 0)` |
| 5 | Avg Hold | `180d` | `AVG(exit_date - entry_date)` in calendar days |
| 6 | Best / Worst | `+31.2% / −24.8%` | `MAX(pnl_pct)` and `MIN(pnl_pct)` |

### Data Requirements

All computations are derived from the `closed_positions` table:

| Field | Description | Source |
|-------|-------------|--------|
| `symbol` | Security symbol | `closed_positions.symbol` |
| `entry_date` | Date position was opened | `closed_positions.entry_date` |
| `exit_date` | Date position was closed | `closed_positions.exit_date` |
| `entry_price` | Average cost basis at entry | `closed_positions.entry_price` |
| `exit_price` | Average sale price | `closed_positions.exit_price` |
| `realized_pnl_pct` | `(exit_price - entry_price) / entry_price * 100` | Computed |
| `realized_pnl_dollar` | `shares * (exit_price - entry_price)` | Computed |
| `hold_days` | `exit_date - entry_date` | Computed |
| `exit_reason` | Why the position was closed | `closed_positions.exit_reason` |
| `sector` | GICS sector of the security | `securities.sector` via join |
| `dividends_received` | Total dividend income while position was open | `SUM(transactions.amount) WHERE ticker = X AND category = 'income' AND date BETWEEN entry_date AND exit_date` |
| `fees_paid` | ADR fees + foreign tax while position was open | `SUM(transactions.amount) WHERE ticker = X AND category = 'fee' AND date BETWEEN entry_date AND exit_date` |
| `total_return_dollar` | Price P&L + dividends − fees | `realized_pnl_dollar + dividends_received + fees_paid` |

**Note on cost basis**: The `entry_price` may be adjusted by `corporate_action` transactions (Return Of Capital, Return Of Cap Adj) that reduce cost basis on the referenced security. The import pipeline should apply these adjustments to `positions.cost_basis` when they occur.

### Backend Computation

```
GET /api/closed/summary

Response:
{
  total_realized_pnl: number,   // Dollar total
  avg_return_pct: number,       // Average return %
  win_rate_pct: number,         // Win rate %
  win_count: number,
  loss_count: number,
  avg_win_pct: number,          // Average winning return %
  avg_loss_pct: number,         // Average losing return %
  avg_hold_days: number,        // Average holding period
  best_return_pct: number,      // Best single trade
  worst_return_pct: number      // Worst single trade
}
```

---

## 4.2 Trade Log

**Visual**: Scrollable table of all closed positions, sorted by exit date descending (most recent first). Each row has a left-border color indicator: green for winners, red for losers.

**Toggle**: `Table` / `Analytics` — switches between the tabular view and the chart view (Section 4.3).

### Table Columns

| Column | Description | Alignment |
|--------|-------------|-----------|
| Symbol | Symbol (monospace bold) | Left |
| Sector | GICS sector | Left |
| Strategy | Parent strategy name (links to Module 6 detail). Shows "—" if unassigned. | Left |
| Entry | Entry date (YYYY-MM-DD) | Right |
| Exit | Exit date (YYYY-MM-DD) | Right |
| Entry $ | Average entry price | Right |
| Exit $ | Average exit price | Right |
| Return | P&L % (green/red, bold) | Right |
| P&L | Dollar P&L (with ± prefix) | Right |
| Hold | Holding period in days | Right |
| Reason | Exit reason (color-coded) | Right |

**Exit reason colors**: "Stop loss" → red, "Thesis broken" → amber, "Reconstruction" → purple (strategy was reconstructed, position rotated out), all others → neutral.

### Backend Computation

```
GET /api/closed/trades?sort=exit_date&dir=desc

Response:
{
  trades: [
    {
      symbol: string,
      sector: string,
      strategy_id: string | null,
      strategy_name: string | null,
      entry_date: string,
      exit_date: string,
      entry_price: number,
      exit_price: number,
      return_pct: number,
      pnl_dollar: number,
      hold_days: number,
      exit_reason: string
    }
  ]
}
```

---

## 4.3 Analytics View

**Visual**: When the toggle is set to "Analytics," the trade log is replaced by a 2-column grid of charts.

### 4.3.1 Return Distribution (Bar Chart)

Waterfall bar chart showing each closed trade's return, sorted from highest to lowest. Green bars for winners, red for losers. Zero line as reference.

- X-axis: Symbol labels.
- Y-axis: Return percentage.
- Color: Green (`#0A7B4F`) if ≥ 0, Red (`#C8220D`) if < 0, opacity 0.6.

### 4.3.2 Hold Time vs Return (Scatter Plot)

Scatter chart plotting each closed trade as a dot.
- X-axis: Hold days.
- Y-axis: Return %.
- Color: Green if profitable, red if loss.
- Zero line as reference.

**Insight**: This chart reveals whether patience is rewarded (are longer-held positions more profitable?) or whether quick exits preserve capital.

### Backend Computation

```
GET /api/closed/analytics

Response:
{
  return_distribution: [
    { symbol: string, return_pct: number }
  ],
  hold_vs_return: [
    { symbol: string, hold_days: number, return_pct: number }
  ]
}
```

---

## 4.4 Exit Analysis

**Visual**: List showing performance aggregated by exit reason.

| Reason | Count | Avg Return | Win/Total |
|--------|-------|-----------|-----------|
| Target hit | 5 | +22.2% | 5/5 |
| Stop loss | 3 | −15.5% | 0/3 |
| Thesis broken | 2 | −7.3% | 0/2 |
| Rebalance | 1 | +9.8% | 1/1 |
| Valuation stretch | 1 | +18.7% | 1/1 |

**Computation**: `GROUP BY exit_reason`, then compute `COUNT`, `AVG(return_pct)`, `COUNT(return_pct > 0)`.

### Backend Computation

```
GET /api/closed/exit-analysis

Response:
{
  reasons: [
    {
      reason: string,
      count: number,
      avg_return_pct: number,
      win_count: number
    }
  ]
}
```

---

## 4.5 Lessons Panel

**Visual**: A list of qualitative insights derived from the trade data, each with a color-coded left border (green = positive lesson, amber = warning/improvement area).

### Lesson Generation Logic

Lessons are generated by rule-based analysis of the closed positions data:

1. **Discipline check**: If avg return for "Target hit" exits is > 15%, display: "Target hit avg +{X}% — discipline works." (green)
2. **Stop loss calibration**: If avg return for "Stop loss" exits is worse than −12%, display: "Stop loss avg {X}% — tighten?" (amber)
3. **Patience analysis**: Compare avg hold days for winners vs losers. If winners held longer, display: "Winners held {X}d vs losers {Y}d." (green)
4. **Best sector**: Find sector with highest net realized P&L. Display: "Best sector: {sector} (+${X}K)." (green)
5. **Worst single loss**: If worst trade exceeds −20%, display: "Worst single: {symbol} {X}%." (amber)

### Backend Computation

```
GET /api/closed/lessons

Response:
{
  lessons: [
    { text: string, type: "good" | "warning" }
  ]
}
```

---

## Database Tables Involved (All Sections)

- `closed_positions` (symbol, entry_date, exit_date, entry_price, exit_price, shares, exit_reason, strategy_id, reconstruction_period)
- `securities` (sector, industry) — for sector attribution
- `strategies` (strategy_id, name) — for strategy name display
- `transactions` (ticker, category, amount, date) — for per-position dividend income (`category = 'income'`), fee attribution (`category = 'fee'`), and cost basis adjustments (`category = 'corporate_action'`)

---

## Frontend State

| State Variable | Type | Default | Controls |
|----------------|------|---------|----------|
| `closedView` | `"table" \| "chart"` | `"table"` | Toggle between trade log and analytics charts |
