import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `pipeline.*` imports

import streamlit as st

try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except FileNotFoundError:
    pass

from pipeline.config import ANTHROPIC_API_KEY, load_watchlist
from pipeline.fund_discovery import discover_feeds
from pipeline.storage import deactivate_watched_fund, get_watched_funds, upsert_watched_fund

st.set_page_config(page_title="Manage Watchlist — VC Pulse Tracker", page_icon="📈", layout="wide")
st.sidebar.markdown("### 📈 VC Pulse Tracker")
st.title("🔎 Manage Watchlist")

st.subheader("Discover a fund's content")
st.caption("Paste a fund's website — this looks for an RSS/Atom feed directly, and falls "
           "back to an LLM reading the homepage's links for blog/news/portfolio pages if "
           "none is found. A fund gets added to the watchlist either way — with a dedicated "
           "feed if one exists, or press-only (matched via the general press feeds) if not.")

if not ANTHROPIC_API_KEY:
    st.warning("No `ANTHROPIC_API_KEY` configured — RSS autodiscovery still works, but the "
               "LLM fallback (for sites with no direct feed) is disabled.")

with st.form("discover_form"):
    col1, col2 = st.columns([1, 2])
    fund_name = col1.text_input("Fund name", placeholder="Sequoia Capital")
    site_url = col2.text_input("Website URL", placeholder="https://www.sequoiacap.com")
    submitted = st.form_submit_button("Discover", type="primary")

if submitted:
    if not fund_name or not site_url:
        st.error("Both fund name and website URL are required.")
    else:
        with st.spinner(f"Looking for {fund_name}'s feed..."):
            st.session_state["discovery_result"] = discover_feeds(site_url, fund_name)
            st.session_state["discovery_fund_name"] = fund_name
            st.session_state["discovery_site_url"] = site_url

result = st.session_state.get("discovery_result")
if result:
    fund_name = st.session_state["discovery_fund_name"]
    site_url = st.session_state["discovery_site_url"]
    confirmed = result["confirmed_feeds"]
    candidates = result["candidate_pages_no_feed"]

    if confirmed:
        st.success(f"Found {len(confirmed)} feed(s) for {fund_name}.")
        for feed in confirmed:
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{feed['feed_url']}**")
                if c2.button("Add to tracking", key=f"add_{feed['feed_url']}"):
                    upsert_watched_fund(feed["fund_name"], feed["site_url"], feed["feed_url"])
                    st.success("Added — the next pipeline run will pick it up.")
    else:
        st.info(f"No RSS/Atom feed found for {fund_name}.")
        if st.button(f"Add {fund_name} to watchlist anyway (press-only)"):
            upsert_watched_fund(fund_name, site_url, None)
            st.success(f"{fund_name} added — tracked via the general press feeds, no dedicated feed.")

    if candidates:
        st.caption("Pages that looked relevant but had no discoverable feed (informational only):")
        for url in candidates:
            st.markdown(f"- {url}")

st.divider()

st.subheader("Currently tracked funds")
watched = get_watched_funds()
if watched:
    for fund in watched:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            if fund["feed_url"]:
                c1.markdown(f"**{fund['fund_name']}** — ✅ dedicated feed: {fund['feed_url']}")
            else:
                c1.markdown(f"**{fund['fund_name']}** — press-only (no dedicated feed found)")
            if c2.button("Remove", key=f"remove_{fund['fund_name']}"):
                deactivate_watched_fund(fund["fund_name"])
                st.rerun()
else:
    st.write("None yet — discover one above.")

st.divider()

st.subheader("Static watchlist")
st.caption("Funds/sectors matched against press coverage — edit `config/watchlist.yaml` "
           "in the repo to change this list.")
watchlist = load_watchlist()
st.write("**Funds:** " + ", ".join(watchlist.get("funds", [])))
st.write("**Sectors:** " + ", ".join(watchlist.get("sectors", [])))
