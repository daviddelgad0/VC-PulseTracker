"""Pipeline entry point — run on a schedule (see .github/workflows/pipeline.yml).

Order matters: RSS runs before the founder-signal sources because it's what
discovers/promotes companies into tracked_companies in the first place.
"""
from datetime import date, timedelta

from pipeline.config import load_watchlist
from pipeline.sources import github_activity, job_postings, producthunt, rss_feeds, sec_form_d
from pipeline.storage import (
    get_tracked_companies,
    init_schema,
    promote_tracked_companies,
    upsert_funding_events,
    upsert_press_mentions,
    upsert_product_signals,
)

DAYS = 7


def main() -> None:
    init_schema()
    watchlist = load_watchlist()

    form_d_records = sec_form_d.fetch_recent_form_d(days=DAYS)
    stored = upsert_funding_events(form_d_records)
    print(f"sec_form_d: fetched {len(form_d_records)}, stored {stored}")

    press_records = rss_feeds.fetch_recent_articles(watchlist)
    stored = upsert_press_mentions(press_records)
    print(f"rss_feeds: fetched {len(press_records)}, stored {stored}")

    # Exclude cases where the "company" raising is actually one of the watched
    # funds itself (e.g. "Accel closes $550M India fund") — that's the fund
    # raising a fund, not a portfolio company, and shouldn't get founder-signal
    # tracking (job postings/GitHub) alongside real portfolio companies.
    fund_names_lower = [f.lower() for f in watchlist.get("funds", [])]
    fund_matched_companies = [
        r["company_name"]
        for r in press_records
        if r["matched_funds"]
        and r["company_name"]
        and not any(fund in r["company_name"].lower() for fund in fund_names_lower)
    ]
    promoted = promote_tracked_companies(fund_matched_companies, discovered_via="rss_fund_match")
    print(f"tracked_companies: promoted {promoted} newly-seen companies")

    tracked = get_tracked_companies()
    print(f"tracked_companies: {len(tracked)} active")

    job_records = job_postings.fetch_recent_postings(tracked)
    stored = upsert_product_signals(job_records)
    print(f"job_postings: fetched {len(job_records)}, stored {stored}")

    github_records = github_activity.fetch_recent_activity(tracked)
    stored = upsert_product_signals(github_records)
    print(f"github_activity: fetched {len(github_records)}, stored {stored}")

    since_iso = (date.today() - timedelta(days=DAYS)).isoformat() + "T00:00:00Z"
    ph_records = producthunt.fetch_recent_launches(tracked, since_iso)
    stored = upsert_product_signals(ph_records)
    print(f"producthunt: fetched {len(ph_records)}, stored {stored}")


if __name__ == "__main__":
    main()
