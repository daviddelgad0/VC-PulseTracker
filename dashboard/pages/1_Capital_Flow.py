import os
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `pipeline.*` / `dashboard.*` imports

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except FileNotFoundError:
    pass

from dashboard.theme import ACCENT, style_fig
from pipeline.storage import get_funding_events_since, get_press_mentions_since

st.set_page_config(page_title="Capital Flow — VC Pulse Tracker", page_icon="📈", layout="wide")
st.sidebar.markdown("### 📈 VC Pulse Tracker")
st.title("💰 Capital Flow")

days = st.sidebar.slider("Lookback window (days)", min_value=1, max_value=60, value=14)
since = (date.today() - timedelta(days=days)).isoformat()

funding_events = get_funding_events_since(since)
press_mentions = get_press_mentions_since(since)

st.subheader("SEC Form D raise volume")
st.caption("All private raises — broad signal. Counts filings, not dollar amounts "
           "(the daily index doesn't include raise size).")

if funding_events:
    df = pd.DataFrame(funding_events)
    daily_counts = df.groupby("filed_date").size().reset_index(name="filings")

    fig = go.Figure(go.Bar(
        x=daily_counts["filed_date"], y=daily_counts["filings"],
        marker_color=ACCENT,
        hovertemplate="%{x|%b %d}<br><b>%{y} filings</b><extra></extra>",
    ))
    style_fig(fig, y_title="Filings")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with st.expander("View as table"):
        st.dataframe(daily_counts.rename(columns={"filed_date": "Date", "filings": "Filings"}),
                     use_container_width=True, hide_index=True)
else:
    st.info("No Form D filings in this window.")

st.divider()

st.subheader("Watchlist fund mentions in press")
st.caption("Who's actually deploying capital, per press coverage naming the lead investor.")

fund_counter = Counter()
for mention in press_mentions:
    fund_counter.update(mention["matched_funds"])

if fund_counter:
    fund_df = pd.DataFrame(fund_counter.most_common(), columns=["fund", "mentions"])

    fig = go.Figure(go.Bar(
        x=fund_df["mentions"], y=fund_df["fund"], orientation="h",
        marker_color=ACCENT,
        hovertemplate="<b>%{y}</b>: %{x} mentions<extra></extra>",
    ))
    style_fig(fig, y_title=None)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Mentions")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with st.expander("View as table"):
        st.dataframe(fund_df.rename(columns={"fund": "Fund", "mentions": "Mentions"}),
                     use_container_width=True, hide_index=True)
else:
    st.info("No watchlist fund mentions in press this window. Add more sources on the "
            "**Manage Watchlist** page, or expand config/watchlist.yaml.")
