import os
import re
import pandas as pd
import streamlit as st
from projectdetail import DATA_TIES       # reuse the same mapping
from issueswarnings import issuesinfo

def render(project: dict) -> None:

    folder   = project["folder"]
    csv_path = os.path.join(folder, "Requirements.csv")

    if not os.path.exists(csv_path):
        st.info("Requirements.json data is not available - upload it via **🪄 Edit Data**")
        return

    req_df = pd.read_csv(csv_path)
    st.subheader("Requirements Table", divider="orange")

    requirement_columns = req_df.columns.to_series()

    requirement_columns = requirement_columns.apply(lambda y: re.sub("\s{2,}", " ", y))
    requirement_columns = requirement_columns.apply(lambda y: ''.join(map(lambda x: x if x.islower() else " "+x, y)).strip())

    requirement_columns = requirement_columns.apply(lambda y: re.sub("\s{2,}", " ", y))
    requirement_columns = requirement_columns.apply(lambda y: re.sub("(Req)\s", "Requirement ", y))

    req_df.columns = requirement_columns

    cols = st.columns([0.7,0.3])

    with cols[0]:
        st.dataframe(req_df, hide_index=True, use_container_width=True)
    
    with cols[1]:
        issuesinfo(project, "requirements")