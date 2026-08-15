"""Discovery of a fund's RSS feed, tried in order of cost/reliability:

1. RSS autodiscovery on the fund's own site (free) — a <link rel=alternate>
   tag or a common path.
2. LLM fallback (Claude Haiku, costs a fraction of a cent) — classifies the
   homepage's links to find likely blog/news/portfolio pages when the above
   comes up empty, then autodiscovers on each candidate.

A news-aggregator tag-feed fallback (TechCrunch/Crunchbase News `/tag/<slug>/feed/`)
was tried and reverted — see docs/DECISIONS.md. It resolves and "validates,"
but the underlying tag is loosely scoped (TechCrunch's "benchmark" tag pulls
in unrelated articles that never mention the firm), so it isn't actually the
fund's content, and it's redundant with what the existing press feeds +
text-matching already catch when a real mention exists.

Only confirmed feeds are ever meant to become part of the recurring pipeline
— see pipeline/storage.py's watched_funds table and
dashboard/pages/3_Manage_Watchlist.py, which is what actually persists them.
For funds with no real feed (own or otherwise), the Manage Watchlist page's
"add anyway, press-only" path is the honest answer — tracked via the general
press feeds' name-matching, not a feed that doesn't exist.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from pipeline.config import ANTHROPIC_API_KEY

COMMON_FEED_PATHS = ["/feed", "/feed/", "/blog/feed", "/rss.xml", "/index.xml", "/feed.xml"]
HEADERS = {"User-Agent": "VC Pulse Tracker (fund feed discovery)"}
LLM_MODEL = "claude-haiku-4-5-20251001"
MAX_FEED_STALENESS_DAYS = 180


def _is_valid_feed(url: str) -> bool:
    try:
        parsed = feedparser.parse(url)
    except Exception:
        return False
    if parsed.bozo or not parsed.entries:
        return False

    newest = parsed.entries[0]
    time_struct = newest.get("published_parsed") or newest.get("updated_parsed")
    if not time_struct:
        return True  # no date to check — don't punish a feed for missing metadata
    published_at = datetime(*time_struct[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - published_at <= timedelta(days=MAX_FEED_STALENESS_DAYS)


def _autodiscover_feed(page_url: str) -> Optional[str]:
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=10)
        html = resp.text if resp.status_code == 200 else ""
    except requests.RequestException:
        html = ""

    if html:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("link", rel="alternate"):
            type_attr = link.get("type", "")
            if "rss" in type_attr or "atom" in type_attr:
                candidate = urljoin(page_url, link.get("href", ""))
                if candidate and _is_valid_feed(candidate):
                    return candidate

    parsed = urlparse(page_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in COMMON_FEED_PATHS:
        candidate = base + path
        if _is_valid_feed(candidate):
            return candidate

    return None


def _fetch_homepage_links(site_url: str) -> List[Dict[str, str]]:
    try:
        resp = requests.get(site_url, headers=HEADERS, timeout=10)
    except requests.RequestException:
        return []
    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    links, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(site_url, a["href"])
        if href in seen or not href.startswith("http"):
            continue
        seen.add(href)
        links.append({"text": a.get_text(strip=True)[:80], "href": href})
    return links[:200]  # keep the LLM prompt bounded


def _llm_pick_candidate_pages(site_url: str, links: List[Dict[str, str]]) -> List[str]:
    if not ANTHROPIC_API_KEY or not links:
        return []

    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    links_text = "\n".join(f"- {link['text']!r} -> {link['href']}" for link in links)
    prompt = (
        f"Here are the links found on the homepage of {site_url}, a venture capital "
        f"fund's website.\n\n{links_text}\n\n"
        "Which of these links point to the fund's blog, news, press, insights, or "
        "portfolio index page (a page that lists multiple posts/articles/companies, "
        "not a single article)? Return ONLY a JSON array of up to 5 URLs, most likely "
        "first, with no other text. If none look relevant, return []."
    )
    try:
        response = client.messages.create(
            model=LLM_MODEL, max_tokens=300, messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())  # strip markdown code fence, if any
        urls = json.loads(text)
        return [u for u in urls if isinstance(u, str)][:5]
    except Exception:
        return []


def discover_feeds(site_url: str, fund_name: str) -> Dict:
    """Return {"confirmed_feeds": [{"fund_name","feed_url","site_url"}, ...],
    "candidate_pages_no_feed": [url, ...]}."""
    homepage_feed = _autodiscover_feed(site_url)
    if homepage_feed:
        return {
            "confirmed_feeds": [{"fund_name": fund_name, "feed_url": homepage_feed, "site_url": site_url}],
            "candidate_pages_no_feed": [],
        }

    links = _fetch_homepage_links(site_url)
    candidates = _llm_pick_candidate_pages(site_url, links)

    confirmed_urls_seen = set()
    confirmed_feeds, candidate_pages_no_feed = [], []
    for candidate_url in candidates:
        feed = _autodiscover_feed(candidate_url)
        if feed and feed not in confirmed_urls_seen:
            confirmed_urls_seen.add(feed)
            confirmed_feeds.append({"fund_name": fund_name, "feed_url": feed, "site_url": site_url})
        elif not feed:
            candidate_pages_no_feed.append(candidate_url)

    return {"confirmed_feeds": confirmed_feeds, "candidate_pages_no_feed": candidate_pages_no_feed}
