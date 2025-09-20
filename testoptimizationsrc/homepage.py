import os
import pandas as pd
import streamlit as st
from projectdetail import DATA_TIES       # reuse the same mapping


def render(project: dict) -> None:
    """
    Home Page view.
    • Shows triple‑count if TripleCount.csv exists
    • Otherwise shows the standard missing‑file message
    • Always shows a table of which JSON feeds which tab
    """
    folder   = project["folder"]
    csv_path = os.path.join(folder, "TripleCount.csv")

    if not os.path.exists(csv_path):
        st.info("TripleCount.json data is not available – upload it via **🪄 Edit Data**")
        return

    tc_df = pd.read_csv(csv_path)
    if "tripleCount" in tc_df.columns:
        cnt = tc_df["tripleCount"].iloc[0]
        st.markdown(f"#### RDF Triple Count: :blue[{cnt}]", unsafe_allow_html=True)

    # Tab‑to‑file reference table
    data = [{"Tab Name": tab, "Files Utilized": f"{fname}.json"}
            for tab, files in DATA_TIES.items() for fname in files]
    map_df = pd.DataFrame(data)
    st.markdown("#### Files used in each tab")
    st.dataframe(map_df, hide_index=True, width=550)