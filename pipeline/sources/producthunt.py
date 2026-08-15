"""Product Hunt GraphQL API — new product launches.

Requires a developer token (PRODUCTHUNT_API_TOKEN in .env, from
https://api.producthunt.com/v2/oauth/applications) — optional; if unset this
source is skipped rather than failing the whole pipeline run.

Product Hunt's search doesn't support "posts by company name," so this pulls
recent launches and filters client-side against tracked_companies, the same
approach used for press/RSS fund matching.
"""
from typing import Dict, List

import requests

from pipeline.config import PRODUCTHUNT_API_TOKEN

GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

QUERY = """
query RecentPosts($after: DateTime!) {
  posts(order: NEWEST, postedAfter: $after, first: 50) {
    edges {
      node {
        id
        name
        tagline
        url
        createdAt
      }
    }
  }
}
"""


def fetch_recent_launches(company_names: List[str], since_iso: str) -> List[Dict]:
    """Return recent Product Hunt launches whose name mentions a tracked company.

    Each record: source, source_id, company_name, title, url, published_at.
    """
    if not PRODUCTHUNT_API_TOKEN:
        return []

    resp = requests.post(
        GRAPHQL_URL,
        json={"query": QUERY, "variables": {"after": since_iso}},
        headers={"Authorization": f"Bearer {PRODUCTHUNT_API_TOKEN}"},
        timeout=15,
    )
    if resp.status_code != 200:
        return []

    edges = resp.json().get("data", {}).get("posts", {}).get("edges", [])
    company_names_lower = [name.lower() for name in company_names]

    records: List[Dict] = []
    for edge in edges:
        node = edge["node"]
        matched = next((c for c in company_names_lower if c in node["name"].lower()), None)
        if not matched:
            continue
        records.append(
            {
                "source": "producthunt",
                "source_id": node["id"],
                "company_name": node["name"],
                "title": node.get("tagline"),
                "url": node.get("url"),
                "published_at": node.get("createdAt"),
            }
        )
    return records
