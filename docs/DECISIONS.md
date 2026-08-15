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
