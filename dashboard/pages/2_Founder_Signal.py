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
st.title("Founder / Product Signal")

days = st.sidebar.slider("Lookback window (days)", min_value=1, max_value=60, value=14)
since = (date.today() - timedelta(days=days)).isoformat()

tracked = get_tracked_companies()
signals = get_product_signals_since(since)

st.caption(f"{len(tracked)} tracked companies · {len(signals)} signals since {since}")

if not tracked:
    st.info("No tracked companies yet — these get added automatically when press ties a "
            "company to a watchlist fund (see the Capital Flow page and config/watchlist.yaml).")
elif signals:
    df = pd.DataFrame(signals)[["company_name", "source", "title", "published_at", "url"]]
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Tracked companies exist, but no job postings/GitHub/Product Hunt activity found yet "
            "for them in this window. Job/GitHub sources guess board/org slugs from company names "
            "and will miss companies that use a different slug — see pipeline/sources/job_postings.py.")

st.divider()
st.subheader("Tracked companies")
st.write(", ".join(tracked) if tracked else "None yet.")
