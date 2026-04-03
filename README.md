# Utah CS6960 Trading Agent

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
npm run dev       # Start Vite dev server (HMR enabled)
npm run build     # Production build to dist/
npm run preview   # Serve production build locally
```

### Live Demo

Deployed to GitHub Pages: https://haotsai101.github.io/utah-cs6969-proj/

## Backend

A FastAPI backend for portfolio data, agent endpoints, and related calculations.

### Setup & Commands

```bash
cd backend
pip install -r requirements.txt
python app.py     # Run dev server on http://localhost:8000
```

### Endpoints

- `GET /` – Hello World message
- `GET /api/health` – Health check

## Supabase Stock Tables

The repo now includes a minimal Supabase schema plus a CSV-based workflow for 8 stocks and their March 24 to March 31, 2026 close prices.

### Files

- `backend/supabase/schema.sql` – creates `stocks` and `stock_prices`
- `backend/scripts/fetch_stock_prices_csv.py` – fetches close prices into a reusable CSV
- `backend/scripts/seed_supabase_stocks.py` – seeds 8 symbols and historical close-price rows from CSV
- `backend/.env.example` – required environment variables

The schema uses `stocks.symbol` as the primary key and `stock_prices.stock_symbol` as the foreign key for simpler joins and manual inspection.
Both scripts use the fixed CSV path `backend/data/historical_stock_prices_2026-03-24_2026-03-31.csv`.

### Run It

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

Then set your Supabase project values in `.env`, run the SQL in the Supabase SQL editor, and seed:

```bash
cd backend
python scripts/fetch_stock_prices_csv.py
python scripts/seed_supabase_stocks.py
```

The fetch step writes `backend/data/historical_stock_prices_2026-03-24_2026-03-31.csv`, so you only need to pull the market data once and can reseed the database from that CSV after that.

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
