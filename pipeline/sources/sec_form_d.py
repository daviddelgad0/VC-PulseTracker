"""SEC EDGAR Form D filings — free, public record of private capital raises.

Companies must file a Form D within 15 days of a private securities sale, so
this is a broad, near-real-time feed of "who raised." It does NOT name the
investing funds (Form D's "Related Persons" section covers the issuer's own
officers/directors, not outside investors) — fund attribution comes from
pipeline/sources/rss_feeds.py instead. This source is the supplementary
raise-volume signal, and a way to catch quiet raises press didn't cover.

Pulled from EDGAR's daily filing index rather than the full-text search API,
since the daily index is a stable, documented format that doesn't require a
search query.
"""
import re
from datetime import date, timedelta
from typing import Dict, List

import requests

from pipeline.config import SEC_EDGAR_USER_AGENT

DAILY_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/form.{yyyymmdd}.idx"
)

_HEADER_SEP_RE = re.compile(r"^-{10,}")
_ROW_SPLIT_RE = re.compile(r"\s{2,}")


def _quarter(month: int) -> int:
    return (month - 1) // 3 + 1


def _daily_index_url(d: date) -> str:
    return DAILY_INDEX_URL.format(
        year=d.year, quarter=_quarter(d.month), yyyymmdd=d.strftime("%Y%m%d")
    )


def _fetch_day(d: date) -> List[Dict]:
    resp = requests.get(
        _daily_index_url(d),
        headers={"User-Agent": SEC_EDGAR_USER_AGENT},
        timeout=15,
    )
    if resp.status_code != 200:
        # Weekends/holidays 404. Today's index sometimes isn't published yet
        # and SEC's edge returns 403 rather than 404 in that case. Either way,
        # "no data for this day" rather than a hard failure.
        return []

    lines = resp.text.splitlines()
    start = next((i for i, line in enumerate(lines) if _HEADER_SEP_RE.match(line)), None)
    if start is None:
        return []

    records = []
    for line in lines[start + 1 :]:
        if not line.strip():
            continue
        parts = _ROW_SPLIT_RE.split(line.strip())
        if len(parts) < 5 or parts[0] not in ("D", "D/A"):
            continue
        form_type, company_name, cik, filed_date_raw, file_name = parts[0], parts[1], parts[2], parts[3], parts[4]
        # Normalize "20260813" -> "2026-08-13" (ISO) for consistent DATE storage/comparison.
        filed_date = f"{filed_date_raw[0:4]}-{filed_date_raw[4:6]}-{filed_date_raw[6:8]}"
        records.append(
            {
                "source": "sec_form_d",
                "source_id": file_name,
                "company_name": company_name,
                "form_type": form_type,
                "cik": cik,
                "filed_date": filed_date,
                "url": "https://www.sec.gov/Archives/" + file_name,
            }
        )
    return records


def fetch_recent_form_d(days: int = 7) -> List[Dict]:
    """Return Form D / D-A filings from the last `days` calendar days.

    Each record: source, source_id, company_name, form_type, cik, filed_date, url.
    """
    today = date.today()
    records: List[Dict] = []
    for offset in range(days):
        records.extend(_fetch_day(today - timedelta(days=offset)))
    return records
