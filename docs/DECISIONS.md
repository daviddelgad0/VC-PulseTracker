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

## 2026-08-15 — Fund matching: case-sensitive, word-boundary

Caught live on the deployed dashboard: case-insensitive substring matching was
tagging unrelated AI-model news as "Benchmark" and "NEA" capital-deployment
activity. Two collisions: "Accel" matched inside "accelerator" (fixed by word
boundaries), and "Benchmark" the firm is indistinguishable from "benchmark"
the common word under case-insensitive matching (fixed by matching case-
sensitively — real press mentions of the firm are reliably capitalized,
"Benchmark led the round", while generic usage is usually lowercase,
"AI benchmarks"). `pipeline/sources/rss_feeds.py`'s `_match_terms` now uses
`\bTerm\b` matched against the article text as-is, no `.lower()` on either
side. Re-ran the pipeline after the fix — false positives dropped out, real
matches (Accel, a16z, Lightspeed, Index Ventures) stayed.

## 2026-08-15 — Fund matches gated on a dollar amount in the *headline*

Word-boundary/case-sensitive matching (above) wasn't enough on its own: an
unrelated cybersecurity article ("Four of five enterprises that **secured**
AI agent identities...") still matched "Accel"/"NEA" as capital-flow signal,
and the company-name regex mangled the sentence fragment before "secured"
into a fake company name. "Secured" is a real raise-verb ("secured funding")
but also ordinary English ("secured their systems") — the word alone can't
disambiguate.

Fix: require a `$` amount in the article *title* before accepting any fund
match or attempting company-name extraction — `_looks_like_funding_headline()`
in `pipeline/sources/rss_feeds.py`. Genuine funding headlines state the amount
directly ("X raises $10M"); this also directly fixes the company-name
extraction, since `_COMPANY_RE` now requires `$` right after the raise verb.

First attempt gated on the *summary* instead of the title and was too loose —
these RSS feeds return full article bodies as "summary," dense enough that
unrelated tech articles (API pricing, cost-savings figures) very often
contain some incidental `$` figure of their own (caught this by manually
reviewing what was still matching after the first fix landed — "GLM-5.3...",
"Gemini 3.7 Flash...", "DeepSeek Harness..." were all still false-positively
tagged as fund activity). Title-only is precise because real funding
headlines reliably lead with the number; body text is noisy.

Stale rows already in Postgres from before this fix don't self-correct just
by re-running the pipeline — RSS feeds only carry ~20-30 recent items, so an
older article that's scrolled out of the feed window never gets re-fetched
and re-upserted. Had to explicitly re-score existing `press_mentions` rows
against the new logic and clear `matched_funds` on the ones that no longer
qualify. Worth remembering for any future matching-logic change: fixing the
function isn't enough, existing rows need an explicit backfill pass.

## 2026-08-15 — Job/GitHub slug-guessing: try multiple conventions

`job_postings.py` and `github_activity.py` guess a company's Greenhouse/Lever
board or GitHub org slug from its name — there's no way to look this up
directly. Was only trying one slugification (alphanumeric, no separators);
now also tries a hyphenated form, since that's the other common convention,
and strips legal suffixes ("Inc", "LLC", etc.) before guessing either way.

Correctness note: a candidate slug that resolves (HTTP 200) but currently has
zero open postings/repos is a *real, final* answer, not a miss — the code
must not fall through to the next slug guess in that case, since a coincidental
match on an unrelated company for the next guess is worse than stopping. The
fetch functions return `None` (try the next guess) vs. `[]` (real match,
just empty right now) to keep that distinction explicit.

## 2026-08-15 — Watched funds persist even with no dedicated feed found

`fund_feeds` (feed_url as primary key, one row per confirmed feed) couldn't
represent "I tried to discover this fund, found no feed, but still want it on
the watchlist" — a failed discovery just left no record at all, so e.g.
Sequoia Capital (no discoverable RSS feed anywhere on sequoiacap.com,
confirmed by hand: no `<link rel=alternate>` tag, `/feed` and `/rss.xml` both
redirect to a 404) would vanish from the UI the moment you navigated away.

Replaced with `watched_funds`, keyed on `fund_name` instead, with `feed_url`
nullable. The Manage Watchlist page now has an explicit "Add to watchlist
anyway (press-only)" action when discovery finds nothing — the fund is still
tracked, just relying on the general press feeds' name-matching rather than a
dedicated feed. `get_active_fund_feeds()` (what the pipeline actually polls)
filters to `feed_url IS NOT NULL`, so press-only funds don't break the fetch
loop. Migrated the two existing rows (USV, a16z — a16z's feed was found via
the LLM fallback pointing at their Substack, `a16z.substack.com/feed`) into
the new table; left the old `fund_feeds` table in place unused rather than
dropping it.

## 2026-08-15 — Tried, then reverted: news-tag-feed fallback

Added a third discovery tier for funds like Sequoia/Benchmark with no feed of
their own: TechCrunch and Crunchbase News both expose a feed per tag
(`/tag/<slug>/feed/`) that resolves cleanly and parses as valid RSS for
basically any well-known fund name.

Reverted after checking the actual content, prompted by the user pointing out
"none of these funds have those feeds." They don't — TechCrunch's `benchmark`
tag included "Starcloud raises $170M Series A" and "The leaderboard 'you
can't game'," neither of which mentions the firm anywhere. The tag is a loose
TechCrunch editorial grouping, not "articles about this fund," so presenting
its feed as *the fund's* feed in the UI was actively misleading — even though
downstream word-boundary matching would have silently dropped the unrelated
articles (they don't contain "Benchmark" as a word), the mislabeling itself
was the problem, and the tag content that *did* match would have been
redundant with what the existing press feeds already catch.

Kept one good thing that came out of building this: `_is_valid_feed()` in
`pipeline/fund_discovery.py` now rejects a feed whose most recent entry is
older than 180 days. Found this checking Crunchbase News's tag feeds, which
resolve and parse fine but hadn't posted since 2022 — a real gap the
original "200 + parses" check didn't catch, independent of the tag-feed idea
itself.

For funds with no real feed, the honest answer is the existing "add anyway,
press-only" path on the Manage Watchlist page — tracked via the general press
feeds' name-matching, which is exactly as reliable/unreliable as it always
was, rather than a feed dressed up to look more authoritative than it is.
