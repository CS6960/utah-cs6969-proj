# Utah CS6960 Trading Agent

An equity portfolio management dashboard for a ~$1M portfolio across 200–300 positions, managed by multiple teams using fundamental, systematic, and macroeconomic strategies.

## Project Structure

```
/frontend          - React + Vite single-page application
/backend           - Flask REST API
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

A Flask REST API for portfolio data and calculations.

### Setup & Commands

```bash
cd backend
pip install -r requirements.txt
python app.py     # Run dev server on http://localhost:5000
```

### Endpoints

- `GET /` – Hello World message
- `GET /api/health` – Health check

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
