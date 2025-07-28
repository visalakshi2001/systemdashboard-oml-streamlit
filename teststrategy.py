import os
import re
import streamlit as st
import pandas as pd
import numpy as np
import graphviz
import plotly.express as px
from datetime import datetime
from projectdetail import DATA_TIES     # just to reuse the standard message text
from issueswarnings import issuesinfo

STANDARD_MSG = "{}.json data is not available – upload it via **Edit Data**"

def render(project: dict) -> None:
    """
    Dynamic Test‑Strategy view (metrics · graph · timeline · table).
    Facility names, tests, cases – all come from user CSV.
    """
    folder = project["folder"]
    strat_csv = os.path.join(folder, "TestStrategy.csv")
    fac_csv   = os.path.join(folder, "TestFacilities.csv")
    equip_csv  = os.path.join(folder, "TestEquipment.csv")   # NEW

    # ---------- Guard: are the files present? -------------------------------
    missing = []
    if not os.path.exists(strat_csv):
        missing.append("TestStrategy")
    if not os.path.exists(fac_csv):
        missing.append("TestFacilities")
    if not os.path.exists(equip_csv):
        missing.append("TestEquipment")                       # NEW
    if missing:
        st.info(", ".join(f"{m}.json" for m in missing) + " data is not available – upload it via **Edit Data**")
        return

    # ----- Load & tidy the strategy table, facilities table and equipment table  ------
    strategy = pd.read_csv(strat_csv)
    strategy.columns = (
        strategy.columns.str.replace(r"\s{2,}", " ", regex=True)        # collapse dbl‑spaces
                         .str.replace(r"(?<!^)(?=[A-Z])", " ", regex=True)
                         .str.strip()
                         .str.replace("Org$", "Organization", regex=True)
    )

    facilities = pd.read_csv(fac_csv)
    facilities.columns = (
        facilities.columns.str.replace(r"\s{2,}", " ", regex=True)        # collapse dbl‑spaces
                         .str.replace(r"(?<!^)(?=[A-Z])", " ", regex=True)
                         .str.strip()
                         .str.replace("Org$", "Organization", regex=True)
    )
    
    equipments = pd.read_csv(equip_csv)
    equipments.columns = (
        equipments.columns.str.replace(r"\s{2,}", " ", regex=True)        # collapse dbl‑spaces
                         .str.replace(r"(?<!^)(?=[A-Z])", " ", regex=True)
                         .str.strip()
                         .str.replace("Org$", "Organization", regex=True)
    )

    # ---------- Quick metrics -----------------------------------------------
    strategy["Duration Value"] = pd.to_numeric(strategy["Duration Value"], errors="coerce")
    test_case_durations = strategy.groupby("Test Case")["Duration Value"].max()

    # Build execution sequence (same algorithm as before, but dynamic)
    link = strategy[["Test Case", "Occurs Before"]].dropna()
    parent = dict(zip(link["Test Case"], link["Occurs Before"]))
    head = (set(parent.keys()) - set(parent.values())).pop()
    order = []
    while head:
        order.append(head)
        head = parent.get(head)

    facilities_seq = strategy.set_index("Test Case").loc[order, "Facility"].tolist()

    # Count facility changes for travel time
    loc_change = sum(
        1 for a, b in zip(facilities_seq[:-1], facilities_seq[1:]) if a != b
    )

    total_duration = test_case_durations.sum() + loc_change * 6

    cols = st.columns([0.4, 0.7])

    with cols[0]:
        colm = st.columns(3)
        colm[0].metric("Total Test Duration", f"{int(total_duration)} days")
        colm[1].metric("Total Test Cases", strategy["Test Case"].nunique())
        colm[2].metric(label="Total Tests", value=strategy["Test"].nunique(), delta_color="inverse")
        colm[0].metric("Total Facilities",  facilities["Test Facility"].nunique())
        colm[1].metric(label="Total Test Equipment", value=equipments["Equipment"].nunique(), delta_color="inverse")
        if "Test Procedure" in strategy.columns:
            colm[2].metric(label="Total Test Procedures", value=strategy["Test Procedure"].nunique(), delta_color="inverse")
    with cols[1]:
        issuesinfo(project, "test_strategy")

    st.divider()

    # ---------- Graph view ---------------------------------------------------
    make_graph_view(strategy)

    # ---------- Sequence / timeline view ------------------------------------
    make_sequence_view(strategy, order, test_case_durations, total_duration)

    # ---------- Table explorer ----------------------------------------------
    make_table_view(strategy)

# --------------------------------------------------------------------------- #
# Helper utilities – largely lifted from your earlier code, but made dynamic #
# --------------------------------------------------------------------------- #

def make_table_view(strategy):
    st.markdown("#### Test Strategy Explorer", True)
    subsetstrategy = strategy.drop(columns=["Test Equipment", "Occurs Before"])
    subsetstrategy = subsetstrategy.dropna(axis=1, how="all")
    # save column order for later displaying
    column_order = subsetstrategy.columns
    subsetcols = [col for col in subsetstrategy.columns if col != "Duration Value"]
    subsetstrategy = subsetstrategy.groupby(subsetcols, as_index=False)["Duration Value"].max()
    exp = st.expander("View Entire Test Strategy Table", icon="🗃️")
    exp.dataframe(subsetstrategy[column_order].drop_duplicates(), hide_index=True, use_container_width=True)

    cols = st.columns([0.1,0.9])
    with cols[0]:
        testopt = st.radio("Select Test", options=np.unique(strategy["Test"]), index=0)

        caseopts = strategy[strategy["Test"] == testopt]["Test Case"].value_counts().index.tolist() + ["All"]
        testcaseopt = st.radio("Select Test Case", options=caseopts, index=0)

    with cols[1]:
        if testcaseopt == "All":
            selectedstrategy = strategy[strategy["Test"] == testopt]
        else:
            selectedstrategy = strategy[(strategy["Test"] == testopt) & (strategy["Test Case"] == testcaseopt)]
        st.dataframe(selectedstrategy.drop_duplicates(), hide_index=True, use_container_width=True, height=280)

def make_graph_view(strategy: pd.DataFrame) -> None:
    st.markdown("#### Test Strategy Structure")
    dot = graphviz.Digraph(strict=True)

    for _, row in strategy.iterrows():
        s, t, c = row["Test Strategy"], row["Test"], row["Test Case"]
        if pd.notna(s): dot.node(s)
        if pd.notna(t):
            dot.node(t)
            dot.edge(s, t, label="has test")
        if pd.notna(c):
            dot.node(c, shape="box")
            dot.edge(t, c, label="has test case")

    st.graphviz_chart(dot, use_container_width=True)


def make_sequence_view(strategy, exec_order, duration_dict, total_duration):
    st.markdown("#### Execution Sequence")
    # Build timeline rows
    tl_rows = []
    current_start = pd.to_datetime("2025-01-01")  # any anchor is fine
    prev_facility = None

    durations = duration_dict.to_dict()

    for test in exec_order:
        fac = strategy.loc[strategy["Test Case"] == test, "Facility"].iloc[0]

        # Add a 6‑day transit block if facility changes
        if prev_facility and fac != prev_facility:
            transit_finish = current_start + pd.Timedelta(days=5)
            for f in (prev_facility, fac):
                tl_rows.append(
                    {"Facility": f, "Test Case": "Transit",
                     "Start": current_start, "Finish": transit_finish}
                )
            current_start = transit_finish
        # Normal test row
        dur = durations[test] if durations[test] > 1 else durations[test] + .90
        finish = current_start + pd.Timedelta(days=dur)
        tl_rows.append(
            {"Facility": fac, "Test Case": test,
             "Start": current_start, "Finish": finish}
        )
        current_start = finish
        prev_facility = fac

    tl_df = pd.DataFrame(tl_rows)

    fig = px.timeline(
        tl_df, x_start="Start", x_end="Finish",
        y="Facility", color="Test Case", text="Test Case",
        color_discrete_sequence=px.colors.qualitative.Plotly,
        color_discrete_map={"Transit": "#e4e6eb"},
    )
    # Format X axis as "Day N"
    x_end = int(6 * (total_duration // 6) + 8)
    fig.update_layout(
        bargap=0, showlegend=False,
        xaxis=dict(
            title_text="Day Count",
            tickmode="array",
            tickvals=[pd.to_datetime("2025-01-01") + pd.Timedelta(days=i)
                      for i in range(0, x_end, 6)],
            ticktext=[f"Day {i}" for i in range(0, x_end, 6)],
            range=[pd.to_datetime("2025-01-01"),
                   pd.to_datetime("2025-01-01") + pd.Timedelta(days=x_end)],
        ),
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
