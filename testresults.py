import os
import streamlit as st
import pandas as pd
from issueswarnings import issuesinfo

STANDARD_MSG = "{}.json data is not available – upload it via **Edit Data**"

def render(project: dict) -> None:
    """
    Test‑Results tab: metrics & explorer. Purely visual; nothing mutates state.
    """
    folder = project["folder"]
    csv_path = os.path.join(folder, "TestResults.csv")

    if not os.path.exists(csv_path):
        st.info(STANDARD_MSG.format("TestResults"))
        return

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.replace(r"(?<!^)(?=[A-Z])", " ", regex=True).str.strip()

    st.markdown("#### Test Subject: Lego_Rover")

    # ---- Quick selectors ----------------------------------------------------
    colA, colB = st.columns(2)

    with colA:
        tc_opt = st.selectbox("Select Test Case", df["Test Case"].unique())
        # reset index so that row count in metric loop starts from 0
        show_metrics(df[df["Test Case"] == tc_opt].reset_index(drop=True), case_mode=True)

    with colB:
        attr_opts = (
            df["Test Result"].str.split("_").str[2:].str.join("_").unique()
        )
        attr = st.selectbox("Select Result Attribute", attr_opts)
        # reset index so that row count in metric loop starts from 0
        show_metrics(df[df["Test Result"].str.contains(attr)].reset_index(drop=True), case_mode=False)

    # ---- Full table ---------------------------------------------------------
    exp = st.expander("View Test Results", icon="📊")
    exp.dataframe(df, hide_index=True, use_container_width=True)

    # ---- Issues for this tab -----------------------------------------------
    issuesinfo(project, "test_results")


def show_metrics(subdf: pd.DataFrame, case_mode: bool) -> None:
    cont = st.container(border=True)
    cols = cont.columns(3 if not case_mode else 2)
    for i, row in subdf.iterrows():
        tc, res, val, unit = row["Test Case"], row["Test Result"], row["Test Result Value"], row["Test Result Unit"]
        res_name = res.split(tc + "_")[-1].replace("_", "")
        if case_mode:
            cols[i % 2].metric(label=f"🔭 {tc}", value=f"{val} {unit}", delta=f"🧮 {res_name}")
        else:
            cols[i % 3].metric(label=f"🧮 {res_name}", value=f"{val} {unit}", delta=f"🔭 {tc}")
