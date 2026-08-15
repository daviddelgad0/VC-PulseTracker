import os
import sys
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

from pipeline.storage import get_product_signals_since, get_tracked_companies

st.set_page_config(page_title="Founder Signal — VC Pulse Tracker", page_icon="📈", layout="wide")
st.sidebar.markdown("### 📈 VC Pulse Tracker")
st.title("🚀 Founder / Product Signal")

days = st.sidebar.slider("Lookback window (days)", min_value=1, max_value=60, value=14)
since = (date.today() - timedelta(days=days)).isoformat()

tracked = get_tracked_companies()
signals = get_product_signals_since(since)

kpi_cols = st.columns(3)
for col, (label, value) in zip(kpi_cols, [
    ("Tracked companies", len(tracked)),
    ("Signals this window", len(signals)),
    ("Companies with activity", len({s["company_name"] for s in signals})),
]):
    with col:
        with st.container(border=True):
            st.metric(label, f"{value:,}")

st.write("")

if not tracked:
    st.info("No tracked companies yet — these get added automatically when press ties a "
            "company to a watchlist fund. Add more fund sources on the **Manage Watchlist** page.")
elif signals:
    df = pd.DataFrame(signals)[["company_name", "source", "title", "published_at", "url"]]
    df.columns = ["Company", "Source", "Title", "Published", "Link"]
    st.dataframe(
        df, use_container_width=True, hide_index=True,
        column_config={"Link": st.column_config.LinkColumn(display_text="Open ↗")},
    )
else:
    st.info("Tracked companies exist, but no job postings/GitHub/Product Hunt activity found "
            "yet in this window. Job/GitHub sources guess board/org slugs from company names "
            "and will miss companies using a different slug.")

st.divider()
st.caption("Tracked companies")
st.write(", ".join(tracked) if tracked else "None yet.")
