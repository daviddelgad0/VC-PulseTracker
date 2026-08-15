"""GitHub public API — org repo activity as a technical build signal.

Free, official API. Unauthenticated calls are capped at 60 req/hr; set
GITHUB_TOKEN in .env to raise that to 5000/hr (needed once the tracked-company
list grows past a handful of orgs).

Like job_postings.py, this guesses the GitHub org slug from the company name
and skips misses rather than trying to resolve names properly.
"""
import re
from typing import Dict, List

import requests

from pipeline.config import GITHUB_TOKEN

ORG_REPOS_URL = "https://api.github.com/orgs/{org}/repos?sort=pushed&direction=desc&per_page=5"


def _slugify(company_name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", company_name.lower().replace(" ", "-"))


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def fetch_recent_activity(company_names: List[str]) -> List[Dict]:
    """Return the most-recently-pushed repos for GitHub orgs matching
    company_names (best-effort slug guess).

    Each record: source, source_id, company_name, title, url, published_at.
    """
    records: List[Dict] = []
    for company_name in company_names:
        org = _slugify(company_name)
        if not org:
            continue
        resp = requests.get(ORG_REPOS_URL.format(org=org), headers=_headers(), timeout=10)
        if resp.status_code != 200:
            continue
        for repo in resp.json():
            records.append(
                {
                    "source": "github",
                    "source_id": str(repo["id"]),
                    "company_name": company_name,
                    "title": repo.get("full_name"),
                    "url": repo.get("html_url"),
                    "published_at": repo.get("pushed_at"),
                }
            )
    return records
