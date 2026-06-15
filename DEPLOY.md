# Deployment Guide — Acquisition Engine

> **Platform:** Render (recommended), Railway, or Heroku
> **Not suitable for:** Netlify (Python backend + Playwright)

---

## 1. Project Structure

```
project-2-acquisition-engine/
├── src/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Pydantic settings
│   ├── models.py            # BusinessProfile, DigitalStrategy
│   ├── state_machine.py     # LangGraph pipeline
│   ├── agents/              # Scraper, Auditor, Outreach
│   ├── prompts/             # LLM prompt templates
│   └── utils/               # Maps client, scraper, logger
├── templates/               # Jinja2 templates for PDFs
├── output/                  # Generated JSON + PDFs
├── requirements.txt         # Pip dependencies
├── pyproject.toml           # Poetry metadata + dev deps
├── render.yaml              # Render Blueprint (created)
├── Procfile                 # Heroku/Railway entry (created)
├── .env.example             # Environment template
└── README.md                # Local usage docs
```

---

## 2. Pre-Deployment Checklist

| Item | Status | Notes |
|------|--------|-------|
| `requirements.txt` | ✅ | All runtime deps listed |
| `pyproject.toml` | ✅ | Poetry config present |
| `README.md` | ✅ | Local usage documented |
| `render.yaml` | ✅ | **Created** — Render Blueprint |
| `Procfile` | ✅ | **Created** — Heroku/Railway |
| Playwright browsers | ⚠️ | Install via `playwright install chromium` in build step |
| Environment variables | ⚠️ | Must set `OPENAI_API_KEY` + `GOOGLE_MAPS_API_KEY` |
| Persistent storage | ⚠️ | `output/` dir needs disk or cloud storage |

---

## 3. Environment Variables

Copy `.env.example` and set real values:

```bash
OPENAI_API_KEY=sk-...
GOOGLE_MAPS_API_KEY=AIza...
TARGET_REGION=Cyberjaya
TARGET_COUNTRY=Malaysia
LLM_MODEL=gpt-4o-mini
TEMPERATURE=0.2
```

**On Render:** Set via Dashboard → Environment → Add manually (sync: false in `render.yaml`).

---

## 4. Deploy to Render

### Option A — Blueprint (recommended)

1. Push this repo to GitHub.
2. In Render Dashboard, click **New +** → **Blueprint**.
3. Connect repo → Render reads `render.yaml`.
4. Set secret env vars (`OPENAI_API_KEY`, `GOOGLE_MAPS_API_KEY`).
5. Click **Deploy**.

### Option B — Manual Web Service

1. **New Web Service** → Connect repo.
2. **Runtime:** Python 3
3. **Build Command:**
   ```bash
   pip install -r requirements.txt && playwright install chromium
   ```
4. **Start Command:**
   ```bash
   python -m src.main run --region "$TARGET_REGION" --keywords cafe restaurant lounge
   ```
5. Set env vars in Dashboard.
6. Deploy.

---

## 5. Deploy to Railway

1. Push repo to GitHub.
2. Railway Dashboard → **New Project** → **Deploy from GitHub repo**.
3. Add a **Start Command** in Settings:
   ```bash
   python -m src.main run --region "$TARGET_REGION" --keywords cafe restaurant lounge
   ```
4. Add **Environment Variables** in Railway Dashboard.
5. Add a **Build Command**:
   ```bash
   pip install -r requirements.txt && playwright install chromium
   ```
6. Deploy.

---

## 6. Deploy to Heroku

1. Push repo to GitHub.
2. Heroku Dashboard → **Create New App**.
3. Connect GitHub repo → **Deploy Branch**.
4. Set **Config Vars** in Settings.
5. Add **Buildpack** for Playwright (or use `aptfile` + `heroku-buildpack-apt` for system deps).
6. Deploy.

> ⚠️ **Heroku note:** WeasyPrint + Playwright need system libraries (libglib, libnss, etc.). Use an apt buildpack or Docker deploy.

---

## 7. Important Considerations

### Playwright + Headless Browsers
- **Render:** `playwright install chromium` in build step works on standard plan.
- **Railway:** Same — add to build command.
- **Heroku:** Requires apt buildpack or Docker for system deps.

### Persistent Storage (`output/`)
- Render/Railway/Heroku **ephemeral disks** reset on redeploy.
- **Options:**
  1. Mount a persistent disk (Render Disks, Railway Volumes).
  2. Upload outputs to S3 / Cloudflare R2 / Google Drive.
  3. Webhook results to n8n (see `N8N_WEBHOOK_URL` in `.env.example`).

### Execution Model
- This is a **batch job / CLI tool**, not a long-running web server.
- On Render/Railway, it runs once on start and exits.
- For scheduled runs, use:
  - **Render:** Cron Jobs (separate service type)
  - **Railway:** Scheduler or external cron calling API
  - **Heroku:** Heroku Scheduler add-on

### Health Check
- `render.yaml` sets `healthCheckPath: /` but the app has no HTTP server.
- Either add a minimal Flask/FastAPI health endpoint, or disable health checks.
- **Recommendation:** Wrap with a tiny FastAPI app for health + trigger endpoints.

---

## 8. Quick Start (Post-Deploy)

```bash
# SSH / exec into container
python -m src.main scrape --region "Cyberjaya" --keywords cafe
python -m src.main audit --input output/raw_businesses_*.json
python -m src.main run --region "Cyberjaya" --keywords cafe restaurant lounge
```

---

## 9. Files Created / Modified

| File | Action | Purpose |
|------|--------|---------|
| `render.yaml` | **Created** | Render Blueprint config |
| `Procfile` | **Created** | Heroku / Railway process definition |
| `DEPLOY.md` | **Created** | This deployment guide |

---

## 10. Next Steps

1. Add a lightweight HTTP wrapper (FastAPI/Flask) for health checks and manual triggers.
2. Configure persistent storage or cloud upload for `output/` files.
3. Set up scheduled runs via Render Cron or external scheduler.
4. Add monitoring/logging (e.g., Sentry, Logtail).
