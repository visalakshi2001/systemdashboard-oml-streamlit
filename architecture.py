import os
import pandas as pd
import streamlit as st
import graphviz

def render(project: dict) -> None:
    """
    Architecture view.
    • Uses SystemArchitecture.csv and MissionArchitecture.csv
    • If either missing -> standard message
    • Otherwise draws a graphviz graph selectable by the user
    """
    folder   = project["folder"]
    sys_csv  = os.path.join(folder, "SystemArchitecture.csv")
    miss_csv = os.path.join(folder, "MissionArchitecture.csv")

    missing = []
    if not os.path.exists(sys_csv):
        missing.append("SystemArchitecture.json")
    if not os.path.exists(miss_csv):
        missing.append("MissionArchitecture.json")

    if missing:
        st.info(f"{', '.join(missing)} data is not available – upload it via **Edit Data**")
        return

    df_sys  = pd.read_csv(sys_csv)
    df_miss = pd.read_csv(miss_csv)

    view = st.selectbox("Select view", ["System Architecture", "Mission Architecture"])

    dot = graphviz.Digraph(comment="Architecture", strict=True)

    if view == "System Architecture":
        headers = df_sys.columns.tolist()
        for _, row in df_sys.iterrows():
            prev_node = None
            for header in headers:
                value = row[header]
                if pd.notna(value):
                    node = str(value)
                    dot.node(node)
                    if prev_node is not None:
                        dot.edge(prev_node, node, label=f"has {header.lower()}")
                    prev_node = node
    else:  # Mission Architecture
        headers = df_miss.columns.tolist()
        for _, row in df_miss.iterrows():
            prev_node = None
            for header in headers:
                value = row[header]
                if pd.notna(value):
                    node = str(value)
                    dot.node(node)
                    if prev_node is not None:
                        dot.edge(prev_node, node, label=f"has {header.lower()}")
                    prev_node = node

    st.graphviz_chart(dot, use_container_width=True)





    # if view == "System Architecture":
    #     for _, row in df_sys.iterrows():
    #         soi, subsys, comp = row["SOI"], row["Subsystem"], row["Component"]
    #         if pd.notna(soi):     dot.node(str(soi))
    #         if pd.notna(subsys):
    #             dot.node(str(subsys))
    #             if pd.notna(soi): dot.edge(str(soi), str(subsys), label="has subsystem")
    #         if pd.notna(comp):
    #             dot.node(str(comp))
    #             if pd.notna(subsys): dot.edge(str(subsys), str(comp), label="has component")
    # else:  # Mission Architecture
    #     for _, row in df_miss.iterrows():
    #         mission, env, ent = row["Mission"], row["Env"], row["MissionEntities"]
    #         dot.node(str(mission))
    #         if pd.notna(env):
    #             dot.node(str(env))
    #             dot.edge(str(mission), str(env), label="has environment")
    #         if pd.notna(ent):
    #             dot.node(str(ent))
    #             dot.edge(str(env), str(ent), label="has entity")