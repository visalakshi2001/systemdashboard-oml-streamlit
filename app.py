import os
import pandas as pd
import streamlit as st
from projectdetail import project_form, VIEW_OPTIONS, DATA_TIES, replace_data, error_inspector_form, build_oml_form
import homepage
import architecture
import requirements
import testfacility
import teststrategy
import testresults
import issueswarnings

from utilities import _run_installation_if_streamlit_env


st.set_page_config(page_title="SIE 523 Dashboards", page_icon="🛰️", layout="wide")

def init_session():
    """Ensure all required session_state keys exist."""

    if 'projectlist' not in st.session_state:
        st.session_state['projectlist'] = []
    if 'currproject' not in st.session_state:
        st.session_state['currproject'] = None
    
    if 'omluploaded' not in st.session_state:
        st.session_state.omluploaded = False
    if 'build_code' not in st.session_state:
        st.session_state['build_code'] = None
    if 'build_log_path' not in st.session_state:
        st.session_state['build_log_path'] = None
    if 'sparql_present' not in st.session_state:
        st.session_state['sparql_present'] = False
    if 'query_run_exec' not in st.session_state:
        st.session_state['query_run_exec'] = False
    if 'query_code' not in st.session_state:
        st.session_state['query_code'] = None
    if 'query_log_path' not in st.session_state:
        st.session_state['query_log_path'] = None
    if 'query_results' not in st.session_state:
        st.session_state['query_results'] = None
    if 'dir_tree' not in st.session_state:
        st.session_state['dir_tree'] = []
    if 'sparql_selected_nodes' not in st.session_state:
        st.session_state['sparql_selected_nodes'] = []


def panel():
    with st.sidebar:
        st.subheader("Select Project")
        projectlist = st.session_state['projectlist']
        currproject = st.session_state['currproject']

        if projectlist != []:
            projectnames = [p['name'] for p in projectlist]
            currproject = st.radio("Select Current Project", options=projectnames)
            st.session_state['currproject'] = currproject
        else:
            st.write("Create new dashboard using 'New Project'")


        st.subheader("Preferences")
        newproject = st.button("New Project", )
        changeproject = st.button("Edit Project")

        if newproject:
            project_form(mode=1)
        if changeproject:
            project_form(mode=2)
        
        # --------------- create a gap using container ------------
        st.container(height=65, border=False)
        st.subheader("Have an OML file to build?")
        st.caption("Upload your *.oml* file to build it remotely with Gradle")
        if st.button("Generate Data with OML", icon="🟪"):
            build_oml_form()

        st.subheader("Having problems with OML description?")
        st.caption("Upload your *reasoning.xml* file to easily breakdown your error")
        if st.button("Inspect Error", icon="🔍"):
            error_inspector_form()
        

def show_tab(tab_name, project):
    """
    Dispatch each tab to its own view module.
    Tabs not yet modularised fall back to a simple CSV preview + missing‑file message.
    """
    # ---- 1.  delegated views  ------------------------------------------------
    if tab_name == "Home Page":
        homepage.render(project)          # ./homepage.py
        return
    if tab_name == "Architecture":
        architecture.render(project)      # ./architecture.py
        return
    if tab_name == "Requirements":
        requirements.render(project)
        return
    if tab_name == "Test Facilities":
        testfacility.render(project)
        return
    if tab_name == "Test Strategy":
        teststrategy.render(project)
        return
    if tab_name == "Test Results":
        testresults.render(project)
        return
    if tab_name == "Warnings/Issues":
        issueswarnings.render(project)
        return


    # ---- 2.  generic fallback for other tabs  -------------------------------
    folder = project["folder"]
    for base in DATA_TIES[tab_name]:
        csv_path = os.path.join(folder, f"{base}.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            st.dataframe(df, use_container_width=True)
        else:
            st.info(f"{base}.json data is not available - upload it via **🪄 Edit Data** button")     


def main():
    projectlist = st.session_state['projectlist']
    currproject = st.session_state['currproject']

    if projectlist != []:
        project = [p for p in projectlist if p['name'] == currproject][0]
    
    if currproject == None:
        st.title("Welcome!")
        st.write("Create your first project to get started.")
    else:
        with st.container():
            col1, col2 = st.columns([0.9, 0.15])
            with col1:
                st.header(project["name"], divider='violet')
            with col2:
                if st.button("🪄 Edit Data", type='primary'):
                    replace_data(project) 
        
        if project['views'] != []:
            VIEWTABS = st.tabs(project['views'])
            for i, tab in enumerate(VIEWTABS):
                with tab:
                    show_tab(project["views"][i], project)



if __name__ == "__main__":
    _run_installation_if_streamlit_env()  # Ensure Java/Gradle are installed
    init_session()
    panel()
    main()

    st.markdown(
        """
        <style>
        div[data-testid="stDialog"] div[role="dialog"]:has(.big-dialog) {
            width: 80vw;        }
        </style>
        """,
        unsafe_allow_html=True,
    )