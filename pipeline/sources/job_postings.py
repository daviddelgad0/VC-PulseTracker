"""Job board APIs (Greenhouse, Lever) as a "what are they building" signal —
free, public, unauthenticated JSON APIs once you know a company's board slug.

There's no reliable way to look up a company's board slug from its name, so
this guesses the slug from a slugified company name and skips companies where
that guess 404s. That'll miss real matches (different slug conventions) and
occasionally hit a wrong company (name collision) — acceptable for a personal
signal tool, not something to build a full name-resolution service for.
"""
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


_LEGAL_SUFFIX_RE = re.compile(r"\b(inc|incorporated|llc|corp|corporation|ltd|co)\.?\s*$", re.IGNORECASE)


def _slug_candidates(company_name: str) -> List[str]:
    """A couple of plausible board-slug guesses, tried in order — Greenhouse/
    Lever slugs aren't derivable from a company name with certainty, so this
    tries the two most common conventions rather than just one."""
    name = _LEGAL_SUFFIX_RE.sub("", company_name).strip()
    no_sep = re.sub(r"[^a-z0-9]", "", name.lower())
    hyphenated = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    candidates = [c for c in [no_sep, hyphenated] if c]
    seen = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def _fetch_greenhouse(company_name: str, slug: str) -> Optional[List[Dict]]:
    """Returns None if the slug doesn't resolve to a real board (try the next
    guess), or a list (possibly empty — a real board with no open roles right
    now is a valid, final answer, not a reason to keep guessing)."""
    resp = requests.get(GREENHOUSE_URL.format(slug=slug), timeout=10)
    if resp.status_code != 200:
        return None
    jobs = resp.json().get("jobs", [])
    return [
        {
            "source": "greenhouse",
            "source_id": str(job["id"]),
            "company_name": company_name,
            "title": job.get("title"),
            "url": job.get("absolute_url"),
            "published_at": job.get("updated_at"),
        }
        for job in jobs
    ]


def _fetch_lever(company_name: str, slug: str) -> Optional[List[Dict]]:
    resp = requests.get(LEVER_URL.format(slug=slug), timeout=10)
    if resp.status_code != 200:
        return None
    postings = resp.json()
    if not isinstance(postings, list):
        return None
    records = []
    for posting in postings:
        created_at_ms = posting.get("createdAt")
        published_at = (
            datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc).isoformat()
            if created_at_ms
            else None
        )
        records.append(
            {
                "source": "lever",
                "source_id": posting["id"],
                "company_name": company_name,
                "title": posting.get("text"),
                "url": posting.get("hostedUrl"),
                "published_at": published_at,
            }
        )
    return records


def fetch_recent_postings(company_names: List[str]) -> List[Dict]:
    """Return current open postings for companies in company_names, tried
    against Greenhouse then Lever using a couple of slugified-name guesses
    (first one that 200s wins, per platform).

    Each record: source, source_id, company_name, title, url, published_at.
    """
    records: List[Dict] = []
    for company_name in company_names:
        for slug in _slug_candidates(company_name):
            jobs = _fetch_greenhouse(company_name, slug)
            if jobs is not None:  # a real board was found, even if currently empty
                records.extend(jobs)
                break
        for slug in _slug_candidates(company_name):
            jobs = _fetch_lever(company_name, slug)
            if jobs is not None:
                records.extend(jobs)
                break
    return records
