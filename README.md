# VC Pulse Tracker

A personal dashboard for keeping a finger on the pulse of the VC/startup world:
which top-tier funds are deploying capital where, and what founders at the
resulting companies are actually building.

Two tracks of signal, both surfaced in the dashboard:

1. **Capital deployment** — press coverage naming a watchlist fund, plus SEC
   Form D filings as a broad raise-volume signal.
2. **Founder/product signal** — job postings, GitHub activity, and Product Hunt
   launches for companies discovered via track 1.

## Architecture

```
pipeline (GitHub Actions, daily cron) --writes--> Postgres (Neon) --reads--> dashboard (Streamlit Community Cloud)
```

The pipeline and dashboard run in separate environments (a scheduled GitHub
Actions job vs. a request-driven Streamlit app), so a shared Postgres database
is what connects them — see `docs/DECISIONS.md` for why.

## Data sources (all free, ToS-clean)

| Source | Gives us | Role |
|---|---|---|
| Press/RSS (TechCrunch, VentureBeat, Crunchbase News) | Named funds, round size, sector | Primary capital-flow-by-fund signal |
| SEC EDGAR Form D daily index | Every private raise (company, date, filing link) | Broad raise-volume signal |
| Job board APIs (Greenhouse, Lever) | Hiring patterns | Founder/product-building signal |
| GitHub public API | Org repo/release activity | Founder/product-building signal |
| Product Hunt API | New launches | Founder/product-building signal (needs `PRODUCTHUNT_API_TOKEN`, optional) |

**No LinkedIn scraping** — see `docs/DECISIONS.md`.

Which funds/sectors matter is configured two ways:
- **Static**: `config/watchlist.yaml` — edit freely, no code changes needed.
- **Dynamic**: the **Manage Watchlist** dashboard page — paste a fund's website
  and it discovers their RSS feed (directly, or via an LLM fallback reading
  the site's links) and adds it to the recurring pipeline.

Companies aren't listed manually; they get promoted into the tracked list
automatically once press ties them to a watchlist fund, which is what then
drives job-posting/GitHub/Product Hunt tracking for that company.

## Repo layout

```
config/watchlist.yaml         funds/sectors to track — edit this to retune the tracker
pipeline/
  sources/                     one module per data source, normalized record shape
  fund_discovery.py             paste a fund's URL -> find their RSS feed (LLM-assisted fallback)
  storage.py                    Postgres read/write
  run.py                         entry point the scheduled workflow calls
dashboard/
  theme.py                        shared dark-theme palette + Plotly styling
  app.py                          Weekly Digest (home page)
  pages/1_Capital_Flow.py          Form D volume + fund-mention charts
  pages/2_Founder_Signal.py        job postings / GitHub / Product Hunt feed
  pages/3_Manage_Watchlist.py      discover + manage dynamic fund feeds
.github/workflows/pipeline.yml   daily scheduled pipeline run
docs/DECISIONS.md                 why things are built this way
```

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL (Neon) and SEC_EDGAR_USER_AGENT

python -m pipeline.run              # fetch + store
streamlit run dashboard/app.py      # view locally at localhost:8501
```

## Deployment

- **Pipeline**: runs via the `pipeline.yml` GitHub Actions workflow. Repo
  secrets needed: `DATABASE_URL`, `SEC_EDGAR_USER_AGENT`, `GH_API_TOKEN`
  (optional, raises GitHub API rate limit), `PRODUCTHUNT_API_TOKEN` (optional).
- **Dashboard**: deployed on Streamlit Community Cloud from this repo
  (`dashboard/app.py` as the entry point). Set `DATABASE_URL`,
  `SEC_EDGAR_USER_AGENT`, and `ANTHROPIC_API_KEY` (needed for the Manage
  Watchlist page's LLM fallback) in the app's Secrets (Streamlit Cloud's
  settings UI) — every dashboard page bridges `st.secrets` into env vars so
  `pipeline.config` works unmodified.
