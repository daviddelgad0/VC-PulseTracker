import os
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `pipeline.*` imports

import pandas as pd
import streamlit as st

try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except FileNotFoundError:
    pass

from pipeline.storage import get_funding_events_since, get_press_mentions_since

st.set_page_config(page_title="Capital Flow — VC Pulse Tracker", page_icon="📈", layout="wide")
st.title("Capital Flow")

days = st.sidebar.slider("Lookback window (days)", min_value=1, max_value=60, value=14)
since = (date.today() - timedelta(days=days)).isoformat()

funding_events = get_funding_events_since(since)
press_mentions = get_press_mentions_since(since)

st.subheader("SEC Form D raise volume (all private raises, broad signal)")
if funding_events:
    df = pd.DataFrame(funding_events)
    daily_counts = df.groupby("filed_date").size().rename("filings")
    st.bar_chart(daily_counts)
    st.caption(f"{len(funding_events)} filings since {since}. Note: this counts filings, "
               "not dollar amounts — the daily index doesn't include raise size.")
else:
    st.info("No Form D filings in this window.")

st.divider()

st.subheader("Watchlist fund mentions in press (who's actually deploying capital)")
fund_counter = Counter()
for mention in press_mentions:
    fund_counter.update(mention["matched_funds"])

if fund_counter:
    fund_df = pd.DataFrame(fund_counter.most_common(), columns=["fund", "mentions"]).set_index("fund")
    st.bar_chart(fund_df)
else:
    st.info("No watchlist fund mentions in press this window. Expand config/watchlist.yaml "
            "or the RSS feed list in pipeline/sources/rss_feeds.py if this stays empty.")
