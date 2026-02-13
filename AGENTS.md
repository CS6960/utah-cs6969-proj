# AGENTS.md

Guidelines for Amp agents working on this repository.

## Quick Commands

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
npm run build
npm run preview
```

### Backend (Flask)

```bash
cd backend
pip install -r requirements.txt
python app.py
```

### Git

```bash
git add .
git commit -m "message"
git push origin main
```

## Directory Structure

- **frontend/** – React app, Vite config, styling, components
- **backend/** – Flask routes, business logic, tests
- **infra/** – Docker, deployment configs, CI/CD
- **docs/** – API specs, module specifications, domain documentation
- **.github/workflows/** – GitHub Actions:
  - `frontend.yml` – Runs on `frontend/` changes, deploys to GitHub Pages
  - `backend.yml` – Runs on `backend/` changes, tests Python 3.9–3.12

## Code Style

**Frontend (JavaScript/React):**
- Use JSX for components
- Inline styles via style objects
- Follow existing patterns in `/src`
- No external CSS frameworks (keep it minimal)

**Backend (Python):**
- Use Flask blueprints for modular routes
- Follow PEP 8 style guide
- Add type hints where possible
- Write tests alongside features

## Common Tasks

### Add a Frontend Feature
1. Edit `frontend/src/App.jsx` or create a component
2. Test locally: `cd frontend && npm run dev`
3. Commit and push — GitHub Actions auto-deploys to Pages

### Add a Backend Endpoint
1. Add route to `backend/app.py`
2. Test locally: `cd backend && python app.py`
3. Commit and push — GitHub Actions tests on multiple Python versions

### Update Dependencies
- **Frontend:** `cd frontend && npm install <package>`
- **Backend:** `pip install <package> && pip freeze > backend/requirements.txt`

## Notes

- All styles in frontend are inline (no CSS files)
- No state management library; use React hooks
- No router library; use tab state variable
- Backend API is currently hardcoded mock data; update as needed
