# Decisions log

Kept here instead of scattered across commit messages / chat history, so the
reasoning behind non-obvious choices survives.

## 2026-08-14 — No automated LinkedIn scraping

LinkedIn's User Agreement prohibits automated data collection. *hiQ Labs v.
LinkedIn* established that scraping public profiles isn't CFAA "hacking," but
it did not legalize scraping against LinkedIn's ToS — that's a separate
breach-of-contract exposure, and LinkedIn has continued to sue scrapers and ban
automating accounts since. Third-party "LinkedIn enrichment" APIs (Proxycurl,
PDL, etc.) are doing the same scraping under the hood and carry the same
underlying risk one layer removed.

Founder/product signal is instead built from sources with official, ToS-
compliant APIs: public job board APIs (Greenhouse/Lever), GitHub's public API,
Product Hunt's API, and RSS/press. This covers most of the same "what are they
building" question without the legal exposure.

## 2026-08-14 — Form D doesn't name investors; press does

SEC Form D's daily index (free, public, near-real-time) tells you a company
raised money and roughly when, but not from whom — Form D's "Related Persons"
section covers the issuer's own officers/directors, not outside investors.
So Form D can't answer "is fund X deploying capital here." Press/RSS coverage
routinely names the lead investor, so that's the primary source for
capital-flow-by-fund; Form D is a supplementary broad raise-volume signal and a
way to catch quiet raises press didn't cover.

A related bug worth remembering: the daily index's Date Filed field is
`YYYYMMDD` with no separators (e.g. `20260813`). It must be normalized to ISO
(`2026-08-13`) before storing/comparing — comparing the raw string against an
ISO-formatted date silently "works" some of the time due to ASCII ordering
coincidences, but isn't a real date comparison. See `pipeline/sources/sec_form_d.py`.

## 2026-08-14 — Filter out funds raising their own funds

The company-name extractor over press headlines will sometimes pick up a fund
raising *its own* new fund (e.g. "Accel closes $550M India fund") and treat the
fund as if it were a portfolio company. `pipeline/run.py` filters out any
extracted "company" name that contains a watchlist fund's name before
promoting it to `tracked_companies` — otherwise funds themselves pollute the
founder-signal watchlist (getting job-posting/GitHub lookups run against them).

## 2026-08-14 — Hybrid data sourcing, no Crunchbase (yet)

Budget ceiling is $10–30/mo, which is below Crunchbase's self-serve API
pricing. Sticking to free sources (SEC Form D, RSS, job board/GitHub/Product
Hunt APIs) keeps total cost near $0. Revisit if free sources prove
insufficient for the fund-level detail wanted.

## 2026-08-14 — Pipeline and dashboard run as separate services

Streamlit Community Cloud apps are request-driven and sleep when idle — they
can't reliably run their own cron jobs. So the pipeline runs on a GitHub
Actions schedule (free) and writes to a shared Postgres database (Neon free
tier); the dashboard (Streamlit Community Cloud, free) only reads from it.
SQLite-on-disk doesn't work across this split since the two run in different,
ephemeral environments — hence a real networked Postgres database instead.

## 2026-08-15 — LLM-assisted fund-feed discovery, RSS-only ongoing tracking

The watchlist used to be entirely static (`config/watchlist.yaml`, hand-edited).
`pipeline/fund_discovery.py` adds a second, dynamic path: paste a fund's
website and it tries RSS/Atom autodiscovery first (free), falling back to an
LLM (Claude Haiku, via `ANTHROPIC_API_KEY`) reading the homepage's links to
find likely blog/news/portfolio pages when no feed is directly discoverable.

Deliberately scoped down on two axes:
- **Only confirmed RSS feeds become ongoing tracked sources** (`fund_feeds`
  table). Pages the LLM flags as promising but with no feed are shown once in
  the Manage Watchlist UI and not polled again — building a periodic
  re-crawl-and-diff system for non-feed pages was ruled out as unnecessary
  complexity for v1.
- **Discovery runs synchronously in the dashboard**, triggered by the user
  clicking "Discover" — not part of the scheduled GitHub Actions pipeline. So
  `ANTHROPIC_API_KEY` only needs to be set in Streamlit Cloud's secrets, not as
  a GitHub Actions secret.

Real-world check during development: a16z.com has no discoverable RSS feed at
all (neither a `<link rel=alternate>` tag nor any common feed path) — the LLM
fallback correctly identified `/news-content/`, `/portfolio/`, `/newsletters/`
as candidates, but none of *those* had feeds either, so the honest result is
"no ongoing feed available," not a wrong guess. USV (usv.com) found a working
feed via plain autodiscovery, no LLM call needed — confirms the free path
should stay first, not be skipped in favor of always calling the LLM.

One implementation gotcha: Claude's response to the link-classification prompt
comes wrapped in a ` ```json ` code fence, which broke `json.loads()` silently
(caught by a broad except, returning an empty list with no visible error).
Fixed by stripping the fence before parsing — see `_llm_pick_candidate_pages`.

## 2026-08-15 — Dashboard redesign: committed dark theme, single accent hue

Full visual redesign using the dataviz skill's reference palette (dark
column) — chose to commit to one deliberate dark theme (`.streamlit/config.toml`,
`base = "dark"`) rather than attempt a light/dark auto-flip, which Streamlit's
theming model doesn't cleanly support at the CSS-variable level the skill's
method assumes.

Every chart here (Form D filing counts, fund-mention counts) is a single-series
magnitude comparison, not a multi-series identity comparison — per the skill's
chart-type table that calls for sequential/one-hue treatment, not a per-bar
rainbow. So all charts use one consistent accent color (categorical slot 1,
blue) rather than assigning a different hue per bar/fund, and carry no legend
(a single series doesn't need one). KPI tiles use Streamlit's native
`st.metric` inside a bordered container rather than custom-CSS cards, since
`st.metric` already matches the skill's stat-tile contract (label + value +
optional delta) and avoids fighting Streamlit's internal DOM with brittle CSS
selectors.
