"""Postgres persistence (Neon). One table per record type, keyed on
(source, source_id) so re-running a fetch is idempotent.

Press mentions that name a watched fund promote a row into tracked_companies —
that's what drives which companies get job-posting/GitHub/Product Hunt tracking.
"""
from contextlib import contextmanager
from typing import Dict, Iterable, List, Optional

import psycopg

from pipeline.config import DATABASE_URL

SCHEMA = """
CREATE TABLE IF NOT EXISTS funding_events (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    company_name TEXT,
    form_type TEXT,
    cik TEXT,
    filed_date DATE,
    url TEXT,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS press_mentions (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    company_name TEXT,
    title TEXT,
    summary TEXT,
    url TEXT,
    matched_funds TEXT[],
    matched_sectors TEXT[],
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS tracked_companies (
    company_name TEXT PRIMARY KEY,
    discovered_via TEXT,
    discovered_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS product_signals (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    company_name TEXT,
    title TEXT,
    url TEXT,
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS fund_feeds (
    fund_name TEXT NOT NULL,
    feed_url TEXT NOT NULL,
    site_url TEXT,
    discovered_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN DEFAULT true,
    PRIMARY KEY (feed_url)
);
"""


@contextmanager
def connect():
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)


def upsert_funding_events(records: Iterable[Dict]) -> int:
    rows = [
        (r["source"], r["source_id"], r.get("company_name"), r.get("form_type"), r.get("cik"), r.get("filed_date"), r.get("url"))
        for r in records
    ]
    if not rows:
        return 0
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO funding_events (source, source_id, company_name, form_type, cik, filed_date, url)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (source, source_id) DO UPDATE SET
                 company_name = EXCLUDED.company_name, filed_date = EXCLUDED.filed_date, url = EXCLUDED.url""",
            rows,
        )
    return len(rows)


def upsert_press_mentions(records: Iterable[Dict]) -> int:
    rows = [
        (
            r["source"],
            r["source_id"],
            r.get("company_name"),
            r.get("title"),
            r.get("summary"),
            r.get("url"),
            r.get("matched_funds") or [],
            r.get("matched_sectors") or [],
            r.get("published_at"),
        )
        for r in records
    ]
    if not rows:
        return 0
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO press_mentions (source, source_id, company_name, title, summary, url, matched_funds, matched_sectors, published_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (source, source_id) DO UPDATE SET
                 company_name = EXCLUDED.company_name, title = EXCLUDED.title, summary = EXCLUDED.summary,
                 matched_funds = EXCLUDED.matched_funds, matched_sectors = EXCLUDED.matched_sectors""",
            rows,
        )
    return len(rows)


def promote_tracked_companies(company_names: Iterable[str], discovered_via: str) -> int:
    rows = [(name, discovered_via) for name in set(company_names) if name]
    if not rows:
        return 0
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO tracked_companies (company_name, discovered_via)
               VALUES (%s, %s)
               ON CONFLICT (company_name) DO NOTHING""",
            rows,
        )
    return len(rows)


def upsert_product_signals(records: Iterable[Dict]) -> int:
    rows = [
        (r["source"], r["source_id"], r.get("company_name"), r.get("title"), r.get("url"), r.get("published_at"))
        for r in records
    ]
    if not rows:
        return 0
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO product_signals (source, source_id, company_name, title, url, published_at)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (source, source_id) DO UPDATE SET
                 title = EXCLUDED.title, url = EXCLUDED.url""",
            rows,
        )
    return len(rows)


def add_fund_feed(fund_name: str, feed_url: str, site_url: Optional[str] = None) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO fund_feeds (fund_name, feed_url, site_url)
               VALUES (%s, %s, %s)
               ON CONFLICT (feed_url) DO UPDATE SET is_active = true""",
            (fund_name, feed_url, site_url),
        )


def deactivate_fund_feed(feed_url: str) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE fund_feeds SET is_active = false WHERE feed_url = %s", (feed_url,))


def get_active_fund_feeds() -> List[Dict]:
    with connect() as conn:
        conn.row_factory = psycopg.rows.dict_row
        cur = conn.execute("SELECT * FROM fund_feeds WHERE is_active = true ORDER BY discovered_at DESC")
        return cur.fetchall()


def get_tracked_companies(active_only: bool = True) -> List[str]:
    query = "SELECT company_name FROM tracked_companies"
    if active_only:
        query += " WHERE is_active = true"
    with connect() as conn:
        cur = conn.execute(query)
        return [row[0] for row in cur.fetchall()]


def get_funding_events_since(since_date: str) -> List[Dict]:
    with connect() as conn:
        conn.row_factory = psycopg.rows.dict_row
        cur = conn.execute(
            "SELECT * FROM funding_events WHERE filed_date >= %s ORDER BY filed_date DESC", (since_date,)
        )
        return cur.fetchall()


def get_press_mentions_since(since_date: str) -> List[Dict]:
    with connect() as conn:
        conn.row_factory = psycopg.rows.dict_row
        cur = conn.execute(
            "SELECT * FROM press_mentions WHERE published_at >= %s ORDER BY published_at DESC", (since_date,)
        )
        return cur.fetchall()


def get_product_signals_since(since_date: str) -> List[Dict]:
    with connect() as conn:
        conn.row_factory = psycopg.rows.dict_row
        cur = conn.execute(
            "SELECT * FROM product_signals WHERE published_at >= %s ORDER BY published_at DESC", (since_date,)
        )
        return cur.fetchall()
