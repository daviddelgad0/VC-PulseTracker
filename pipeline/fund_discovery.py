"""LLM-assisted discovery of a fund's blog/news RSS feed from their website.

RSS autodiscovery (free, no LLM call) is tried first — many fund blogs expose
a feed directly via a <link rel=alternate> tag or a common path. If that comes
up empty, an LLM call classifies the homepage's links to find likely
blog/news/portfolio index pages, and each candidate gets a second
autodiscovery pass (blog index pages often expose a feed even when the
homepage doesn't). Only confirmed feeds are ever meant to become part of the
recurring pipeline — see pipeline/storage.py's fund_feeds table and
dashboard/pages/3_Manage_Watchlist.py, which is what actually persists them.
"""
import json
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from pipeline.config import ANTHROPIC_API_KEY

COMMON_FEED_PATHS = ["/feed", "/feed/", "/blog/feed", "/rss.xml", "/index.xml", "/feed.xml"]
HEADERS = {"User-Agent": "VC Pulse Tracker (fund feed discovery)"}
LLM_MODEL = "claude-haiku-4-5-20251001"


def _is_valid_feed(url: str) -> bool:
    try:
        parsed = feedparser.parse(url)
    except Exception:
        return False
    return not parsed.bozo and len(parsed.entries) > 0


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
