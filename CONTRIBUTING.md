# Contributing

Thanks for helping! Issues and pull requests are welcome.

## Set up

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r backend/requirements-dev.txt -r pipeline/requirements-dev.txt
cd frontend && npm ci && cd ..
```

Run the API (`uvicorn backend.app.main:create_app --factory --reload`) and, in another terminal, the frontend dev
server (`cd frontend && npm run dev`, then open http://localhost:5173 - it proxies `/api` to port 8000).

## Before opening a pull request

```bash
ruff check . && ruff format --check pipeline backend && pytest
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

- Keep evaluation honest: every reported number must come from out-of-sample (rolling-origin) forecasts.
- If you change the pipeline, re-run `python -m pipeline run` and commit the regenerated `data/processed/` and
  `docs/MODEL_CARD.md` together with the code.
- Never commit secrets. Configuration goes in environment variables (see `.env.example`).
- Security issues: please follow [SECURITY.md](SECURITY.md) instead of opening an issue.
