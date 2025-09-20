import streamlit as st
import os
import json
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from testoptimizationsrc.makeplots import build_sankey, make_presence_df, style_presence, make_cost_plots, make_cost_histogram



def render(project: dict) -> None:
    folder   = project["folder"]
    csv_path = os.path.join(folder, "Requirements.csv")
    json_path = os.path.join(folder, "Requirements.json")

    if not os.path.exists(json_path):
        st.info("Requirements.json data is not available – upload it via **🪄 Edit Data**")
        return
    
    # # ──────────────────────────── 2.  Load data once ────────────────────────────

    req_data = json.load(open(json_path, "rb+"))

    requirements = {}
    for req in req_data["results"]["bindings"]:
        requirements[req["reqName"]["value"]] = {
            "id": req["reqName"]["value"],
            "scenarios": req["scenarios"]["value"],
            "quantity": req["quaID"]["value"]
        }

    requirements_df = pd.DataFrame.from_dict(requirements, orient="index")
    requirements_df = requirements_df.reset_index(drop=True).rename(columns={"index": "id"})


    scenario_dict = {}
    for req_id, req in requirements.items():
        for situation in req["scenarios"].split(","):
            if situation not in scenario_dict:
                scenario_dict[situation] = set()
            scenario_dict[situation].add(req_id)
    scenario_df = pd.DataFrame(list(scenario_dict.items()), columns=["scenarioID", "requirementIDs"])
    scenario_df["requirementIDs"] = scenario_df["requirementIDs"].apply(lambda x: ",".join(x))

    # # ──────────────────────────── 3.   Sankey  ────────────────────────────
    st.subheader("Select scenario(s) to inspect")
    cho_scenarios = st.multiselect(
        "Scenario ID", sorted(scenario_df["scenarioID"].unique()), max_selections=10
    )
    if cho_scenarios:
        with st.expander("Show plot settings", expanded=False):
            plot_height = st.slider(
                "Set plot size",
                min_value=450, max_value=900, value=600, step=30,)
        fig = build_sankey(scenario_df, requirements_df, cho_scenarios, plot_height=plot_height)
        st.plotly_chart(fig)
    else:
        st.info("⬆️ Pick one or more scenario IDs to show the Sankey.")
    