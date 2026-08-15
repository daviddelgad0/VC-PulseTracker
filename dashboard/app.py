import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `pipeline.*` imports

import streamlit as st

try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except FileNotFoundError:
    pass  # no secrets.toml locally — rely on .env via python-dotenv instead

from pipeline.storage import (
    get_funding_events_since,
    get_press_mentions_since,
    get_product_signals_since,
    get_tracked_companies,
)

st.set_page_config(page_title="VC Pulse Tracker", page_icon="📈", layout="wide")

st.title("📈 VC Pulse Tracker — Weekly Digest")

days = st.sidebar.slider("Lookback window (days)", min_value=1, max_value=30, value=7)
since = (date.today() - timedelta(days=days)).isoformat()

funding_events = get_funding_events_since(since)
press_mentions = get_press_mentions_since(since)
product_signals = get_product_signals_since(since)
tracked = get_tracked_companies()

st.caption(f"Since {since} · {len(funding_events)} SEC Form D filings · "
           f"{len(press_mentions)} press articles · {len(tracked)} tracked companies")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Capital deployment")
    fund_mentions = [m for m in press_mentions if m["matched_funds"]]
    if fund_mentions:
        for mention in fund_mentions[:15]:
            funds = ", ".join(mention["matched_funds"])
            st.markdown(f"**{mention['company_name'] or mention['title']}** — {funds}  \n"
                        f"[{mention['title']}]({mention['url']})")
    else:
        st.info("No press coverage mentioning a watchlist fund in this window yet. "
                "See the Capital Flow page for the broader SEC Form D raise volume.")

with col2:
    st.subheader("Founder / product signal")
    if product_signals:
        for signal in product_signals[:15]:
            st.markdown(f"**{signal['company_name']}** — {signal['title']}  \n[link]({signal['url']})")
    else:
        st.info("No founder-signal activity found yet for tracked companies. "
                "Tracked companies grow as press ties them to a watchlist fund — "
                "see config/watchlist.yaml.")

st.divider()
st.subheader("Tracked companies")
st.write(", ".join(tracked) if tracked else "None yet.")
