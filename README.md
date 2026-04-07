# CS 6960 Course Project: Portfolio Research Agent

An equity portfolio management dashboard for a ~$1M portfolio across 200–300 positions, managed by multiple teams using fundamental, systematic, and macroeconomic strategies.

## Project Structure

```
/frontend          - React + Vite single-page application
/backend           - FastAPI backend service
/infra             - Infrastructure and deployment configuration
/docs              - Project specifications and documentation
```

## Frontend

A React 19 dashboard with six tabbed modules: Weekly Review, Risk Analytics, Construction, Closed Positions, Alerts, and Manager Performance. Built with Vite and styled inline.

### Setup & Commands

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev       # Start Vite dev server (HMR enabled)
npm run build     # Production build to dist/
npm run preview   # Serve production build locally
```

To point the local frontend at a deployed backend, set `VITE_API_BASE` in `frontend/.env.local`. An example value is included in `frontend/.env.example`.

## Backend

A FastAPI backend for portfolio data, agent endpoints, and related calculations.

### Service Status

Public uptime status page:

- [UptimeRobot Status Page](https://stats.uptimerobot.com/A5rRf3TXWN)

### Setup & Commands

```bash
cd backend
direnv allow
poetry install
cp .env.example .env.local
poetry run python app.py     # Run dev server on http://localhost:8000
```

The backend uses Uvicorn's default port `8000`.

### Endpoints

- `GET /` – Hello World message
- `GET /api/health` – Health check

## Supabase Stock Tables

The repo now includes a minimal Supabase schema plus a CSV-based workflow for 8 stocks and their March 24 to March 31, 2026 close prices.

### Files

- `backend/supabase/schema.sql` – creates `stocks` and `stock_prices`
- `backend/scripts/fetch_stock_prices_csv.py` – fetches close prices into a reusable CSV
- `backend/scripts/seed_supabase_stocks.py` – seeds 8 symbols and historical close-price rows from CSV
- `backend/scripts/seed_portfolio_state.py` – seeds portfolio positions and cash balances
- `backend/.env.example` – required environment variables

The schema uses `stocks.symbol` as the primary key and `stock_prices.stock_symbol` as the foreign key for simpler joins and manual inspection.
Both scripts use the fixed CSV path `backend/data/historical_stock_prices_2026-03-24_2026-03-31.csv`.

### Run It

```bash
cd backend
direnv allow
poetry install
```

Then set your Supabase project values in `backend/.env.local`, run the SQL in the Supabase SQL editor, and seed:

```bash
cd backend
poetry run python scripts/fetch_stock_prices_csv.py
poetry run python scripts/seed_supabase_stocks.py
poetry run python scripts/seed_portfolio_state.py
```

The fetch step writes `backend/data/historical_stock_prices_2026-03-24_2026-03-31.csv`, so you only need to pull the market data once and can reseed the database from that CSV after that.
The portfolio-state seed script uses the current hardcoded holdings and a configurable `CASH_BALANCES` list in the script. It defaults to one cash row: `USD 0.00`.

## Direnv

This repo uses per-directory `direnv` files:
- [backend/.envrc](/utah-cs6969-proj/backend/.envrc)
- [frontend/.envrc](/utah-cs6969-proj/frontend/.envrc)

Typical local setup:

```bash
cd /utah-cs6969-proj/backend
direnv allow

cd /utah-cs6969-proj/frontend
direnv allow
```

After that, each directory loads `.env.local` when present, and falls back to `.env`.

## Development Workflow

1. Create feature branch from `main`
2. Make changes in `frontend/` or `backend/`
3. Push to trigger GitHub Actions:
   - Frontend changes → Build and deploy to GitHub Pages
   - Backend changes → Run tests on Python 3.9–3.12

## Documentation

See `/docs` for detailed module specifications:
- `00-OVERVIEW.md` – Global config, database schema, API endpoints
- `01-WEEKLY-REVIEW.md` through `06-MANAGER-PERFORMANCE.md` – Per-module specs
