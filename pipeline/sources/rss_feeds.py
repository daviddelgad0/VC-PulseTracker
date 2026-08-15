"""Press/RSS feeds — the primary capital-flow-by-fund signal.

Unlike SEC Form D, press coverage routinely names the lead investor, which is
what lets us answer "is fund X deploying capital here." Articles get matched
against config/watchlist.yaml's funds/sectors by simple case-insensitive
substring matching on title+summary — good enough for a personal signal tool,
no NLP dependency needed.

Company name extraction is a best-effort regex over common headline patterns
("X raises $Y", "X lands $Y from Z") — it won't catch every headline, but it's
enough to seed pipeline.storage.promote_tracked_companies for the founder-
signal sources.
"""
import re
from typing import Dict, List, Optional

import feedparser

FEEDS = {
    "techcrunch_venture": "https://techcrunch.com/category/venture/feed/",
    "venturebeat": "https://venturebeat.com/feed/",
    "crunchbase_news": "https://news.crunchbase.com/feed/",
}

_RAISE_VERBS = r"raises?|raised|lands?|landed|secures?|secured|closes?|closed|nabs?|nabbed|scores?|scored"
_COMPANY_RE = re.compile(rf"^([A-Z][A-Za-z0-9&.,'\-\s]{{1,60}}?)\s+(?:{_RAISE_VERBS})\s", re.IGNORECASE)


def _extract_company_name(title: str) -> Optional[str]:
    match = _COMPANY_RE.match(title or "")
    return match.group(1).strip() if match else None


def _match_terms(text: str, terms: List[str]) -> List[str]:
    # Case-sensitive, word-boundary matching. Case-insensitive substring
    # matching false-positived hard on fund names that are also common English
    # words used in unrelated contexts — "Benchmark" (the firm) vs. "benchmark"
    # (AI model benchmarks), "Accel" as a substring of "accelerator". Real firm
    # mentions are reliably capitalized in press ("Benchmark led the round"),
    # so case-sensitivity is actually the disambiguating signal here, not
    # noise — see docs/DECISIONS.md.
    text = text or ""
    return [term for term in terms if re.search(rf"\b{re.escape(term)}\b", text)]


def fetch_recent_articles(watchlist: dict, extra_feeds: Optional[Dict[str, str]] = None) -> List[Dict]:
    """Return recent articles across FEEDS plus extra_feeds (dynamically
    discovered fund feeds, see pipeline/fund_discovery.py), tagged with any
    watchlist funds/sectors they mention.

    Each record: source, source_id (article link), company_name (best-effort),
    title, summary, url, matched_funds, matched_sectors, published_at.
    """
    funds = watchlist.get("funds", [])
    sectors = watchlist.get("sectors", [])

    all_feeds = {**FEEDS, **(extra_feeds or {})}

    records: List[Dict] = []
    for feed_name, feed_url in all_feeds.items():
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            combined = f"{title} {summary}"

            records.append(
                {
                    "source": f"rss:{feed_name}",
                    "source_id": entry.get("link"),
                    "company_name": _extract_company_name(title),
                    "title": title,
                    "summary": summary,
                    "url": entry.get("link"),
                    "matched_funds": _match_terms(combined, funds),
                    "matched_sectors": _match_terms(combined, sectors),
                    "published_at": entry.get("published"),
                }
            )
    return records
