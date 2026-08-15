"""GitHub public API — org repo activity as a technical build signal.

Free, official API. Unauthenticated calls are capped at 60 req/hr; set
GITHUB_TOKEN in .env to raise that to 5000/hr (needed once the tracked-company
list grows past a handful of orgs).

Like job_postings.py, this guesses the GitHub org slug from the company name
and skips misses rather than trying to resolve names properly.
"""
import re
from typing import Dict, List, Optional

import requests

from pipeline.config import GITHUB_TOKEN

ORG_REPOS_URL = "https://api.github.com/orgs/{org}/repos?sort=pushed&direction=desc&per_page=5"

_LEGAL_SUFFIX_RE = re.compile(r"\b(inc|incorporated|llc|corp|corporation|ltd|co)\.?\s*$", re.IGNORECASE)


def _org_candidates(company_name: str) -> List[str]:
    name = _LEGAL_SUFFIX_RE.sub("", company_name).strip()
    hyphenated = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    no_sep = re.sub(r"[^a-z0-9]", "", name.lower())
    candidates = [c for c in [hyphenated, no_sep] if c]
    seen = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def _fetch_org_repos(company_name: str, org: str) -> Optional[List[Dict]]:
    """Returns None if the org doesn't exist (try the next guess), or a list
    (possibly empty — a real org with no public repos is a valid answer)."""
    resp = requests.get(ORG_REPOS_URL.format(org=org), headers=_headers(), timeout=10)
    if resp.status_code != 200:
        return None
    return [
        {
            "source": "github",
            "source_id": str(repo["id"]),
            "company_name": company_name,
            "title": repo.get("full_name"),
            "url": repo.get("html_url"),
            "published_at": repo.get("pushed_at"),
        }
        for repo in resp.json()
    ]


def fetch_recent_activity(company_names: List[str]) -> List[Dict]:
    """Return the most-recently-pushed repos for GitHub orgs matching
    company_names (best-effort slug guess, a couple of conventions tried).

    Each record: source, source_id, company_name, title, url, published_at.
    """
    records: List[Dict] = []
    for company_name in company_names:
        for org in _org_candidates(company_name):
            repos = _fetch_org_repos(company_name, org)
            if repos is not None:
                records.extend(repos)
                break
    return records
