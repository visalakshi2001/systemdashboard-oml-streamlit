
import streamlit as st
import os
import json
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from testoptimizationsrc.src.generate_tests import generate_tests
from jsontocsv import json_to_csv
# from makeplots import build_sankey, make_presence_df, style_presence, make_cost_plots, make_cost_histogram


def render(project: dict) -> None:
    folder   = project["folder"]
    csv_path = os.path.join(folder, "Requirements.csv")
    json_path = os.path.join(folder, "Requirements.json")

    if not os.path.exists(json_path):
        st.info("Requirements.json data is not available – upload it via **🪄 Edit Data**")
        return

    json_to_csv(json_input_path=json_path, csv_output_path=csv_path)

    req_data = json.load(open(json_path, "rb+"))
    tests_data = generate_tests(req_data)

    with open(os.path.join(folder, "tests.json"), "w") as f:
        json.dump(tests_data, f, indent=2)
        print(f"Wrote tests.json to {os.path.join(folder, 'tests.json')}")


    requirements = {}
    for req in req_data["results"]["bindings"]:
        requirements[req["reqName"]["value"]] = {
            "id": req["reqName"]["value"],
            "scenarios": req["scenarios"]["value"],
            "quantity": req["quaID"]["value"]
        }

    requirements_df = pd.DataFrame.from_dict(requirements, orient="index")
    requirements_df = requirements_df.reset_index(drop=True).rename(columns={"index": "id"})

    st.subheader("Which quantities satisfy a requirement?")
    req_id = st.multiselect(
        "Requirement ID", sorted(requirements_df["id"].unique()), key="req_quant_select"
    )
    if req_id != []:
        st.dataframe(requirements_df.query("id in @req_id")[["id", "quantity"]], use_container_width=True, hide_index=True)
    else:
        st.info("⬆️ Pick one or more requirement IDs to show the quantities that satisfy them.")

    with st.expander("Show all requirements and their quantities", icon="📜"):
        st.dataframe(requirements_df[["id", "quantity"]], use_container_width=True, hide_index=True)
