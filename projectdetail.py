import streamlit as st
import pandas as pd
import os
import shutil
from jsontocsv import json_to_csv

import io
import xml.etree.ElementTree as ET
from generate_error import parse_failure_block, failure_to_dataframe, natural_language_message

from pathlib import Path
from utilities import (
    session_tmp_dir,
    discover_json_basenames,
    suggest_tabs_from_json,
    discover_populated_json_basenames,
    match_profile_from_basenames,
    view_name_to_module_name,
)


VIEW_OPTIONS = [
    "Architecture",
    "Requirements",
    "Test Strategy",
    "Test Results",
    "Test Facilities",
    "Warnings/Issues",
]
REPORTS_ROOT = Path("reports")                           #  ./reports/…
DATA_TIES = {
    "Home Page": ["TripleCount"],
    "Test Facilities": ["TestFacilities", "TestEquipment", "TestPersonnel"],
    "Requirements": ["Requirements"],
    "Architecture": ["SystemArchitecture", "MissionArchitecture"],
    "Test Strategy": ["TestStrategy", "TestEquipment", "TestFacilities"],
    "Test Results": ["TestResults"],
    # (Warnings/Issues pulls from these same files, so no separate entry needed)
}

# ---------------------- Dashboard profiles (profile metadata) ----------------
# Each profile lists:
#  - "data": required JSON basenames produced by SPARQL queries
#  - "views": suggested view/tab names for that profile
#  - "module_prefix": optional Python package/folder that contains view modules
#
# module_prefix = None => use the app's global/top-level view modules
#
DASHBOARD_PROFILES = {
    "Lego Rover": {
        "data": [
            "SystemArchitecture",
            "MissionArchitecture",
            "Requirements",
            "TestFacilities",
            "TestEquipment",
            "TestPersonnel",
            "TestStrategy",
            "TestResults",
            "TripleCount",
        ],
        "views": [
            "Architecture",
            "Requirements",
            "Test Facilities",
            "Test Strategy",
            "Test Results",
            "Scenarios",
        ],
        "module_prefix": None,  # use global view modules
        # Optional per-view data-ties overrides for this profile.
        # If not present, global DATA_TIES entries are used.
        "view_data_ties": {
            # Use existing ties (same as global) — you can omit entries that match global
            "Architecture": ["SystemArchitecture", "MissionArchitecture"],
            "Requirements": ["Requirements"],
            "Test Facilities": ["TestFacilities", "TestEquipment", "TestPersonnel"],
            "Test Strategy": ["TestStrategy", "TestEquipment", "TestFacilities"],
            "Test Results": ["TestResults"],
            "Home Page": ["TripleCount"],
        },
    },
    "Test Optimization": {
        "data": [
            "sufficient",
            "Requirements",
            "observationCosts",
            "scenarioCosts",
            "TripleCount",
        ],
        "views": [
            "Test Strategy",
            "Requirements",
            "Scenarios",
        ],
        "module_prefix": "testoptimizationsrc",
        # Profile-specific mapping: Test Strategy here requires different JSONs
        "view_data_ties": {
            "Test Strategy": ["sufficient", "scenarioCosts", "observationCosts", "Requirements"],
            "Requirements": ["Requirements"],
            "Scenarios": ["scenarioCosts"],  # example; update as needed
            "Home Page": ["TripleCount"],
        },
    },
    # Add additional profiles here as needed.
}
# --------------------------------------------------------------------------- #


@st.dialog("Project Details")
def project_form(mode, *, json_dir: str | None = None):
    """
    Modes:
      1 or "new_blank"   -> existing new dashboard form (no JSON processing)
      "crud_dashboard"   -> Edit the Name/Desc/Views of Dashboard or delete dashboard
      "from_retained"    -> read JSONs from st.session_state.retained_json_dir
      "from_uploads"     -> read JSONs from 'json_dir' (staged upload dir)
    """
    # -------------------- NEW JSON-backed creation modes --------------------
    if mode in ("from_retained", "from_uploads"):
        # Resolve source dir
        if mode == "from_retained":
            src_dir = st.session_state.get("retained_json_dir")
            if not src_dir:
                st.error("No retained SPARQL results found in this session.")
                st.stop()
            src_dir = Path(src_dir)
        elif mode == "from_uploads":
            json_dir = st.session_state.get("uploaded_json_dir")
            if not json_dir:
                st.error("No uploaded JSON directory provided.")
                st.stop()
            src_dir = Path(json_dir)

        # Discover JSONs and suggest tabs
        basenames = discover_json_basenames(src_dir)

        # If we have a retained profile in session, prefer that profile's view ties (overrides)
        # Build an effective ties mapping to pass into suggest_tabs_from_json
        effective_ties = dict(DATA_TIES)  # shallow copy of global ties
        retained_profile = st.session_state.get("retained_profile")
        if retained_profile:
            profile_ties = DASHBOARD_PROFILES.get(retained_profile, {}).get("view_data_ties", {})
            # overlay/replace entries for views that the profile provides
            for k, v in profile_ties.items():
                effective_ties[k] = list(v)
        suggested = suggest_tabs_from_json(basenames, effective_ties)

        st.write("Create a dashboard from SPARQL JSON results.")
        st.caption("**Home Page** is always included.")

        with st.form("new_proj_from_json_form"):
            name = st.text_input("Project (Dashboard) Name **:red[*]**", key=f"project_name_{mode}")
            description = st.text_area("Project Description", key=f"project_description_{mode}")

            if not basenames:
                st.warning("No JSON files detected. Upload or generate SPARQL results first.")
                disabled = True
            else:
                disabled = False
            
            if mode in ("from_retained", "from_uploads"):
            # if mode == "from_retained":
                allowed_views = st.session_state.get("retained_allowed_views")
                suggested_views = st.session_state.get("retained_suggested_views")
                if allowed_views is None:
                    allowed_views = [v for v in VIEW_OPTIONS if v != "Home Page"]
                if suggested_views is None:
                    suggested_views = suggested
            else:
                allowed_views = [v for v in VIEW_OPTIONS if v != "Home Page"]
                suggested_views = suggested

            views = st.multiselect(
                "Select views to include",
                options=allowed_views,
                default=suggested_views,
                key=f"project_views_{mode}",
            )

            submitted = st.form_submit_button("Create Project", disabled=disabled)
            if submitted:
                if name == "":
                    st.write("❗ :red[Name cannot be empty]")
                    st.stop()
                
                # 🚫 Duplicate‑name guard (exclude the record being edited)
                if any(p["name"].lower() == name.lower() for p in st.session_state['projectlist']):
                    st.error(f"A project called **{name}** already exists. Pick another name.")
                    st.stop()

                # Create the project folder
                project_folder = Path(os.path.join(REPORTS_ROOT, name.lower().replace(" ", "_")))
                os.makedirs(project_folder, exist_ok=True)

                copied = []
                for jsonfile in Path(src_dir).rglob("*.json"):
                    dest = project_folder / jsonfile.name
                    shutil.copy2(jsonfile, dest)
                    copied.append(dest)

                # 3) Convert each JSON -> CSV beside it
                for dest in copied:
                    csv_out = dest.with_suffix(".csv")
                    try:
                        json_to_csv(csv_output_path=str(csv_out), json_input_path=str(dest))
                    except Exception as e:
                        # Do not fail the whole materialization if one file is bad
                        print(f"CSV Conversion Error: Failed to convert {dest.name}: {e}")

                # project = {
                #     "id": None,  # filled by caller to keep existing numbering logic, if needed
                #     "name": name.strip(),
                #     "description": description,
                #     "views": ["Home Page"] + list(views),
                #     "folder": str(project_folder),
                # }
                project = {
                    "id": None,
                    "name": name.strip(),
                    "description": description,
                    "views": ["Home Page"] + list(views),
                    "folder": str(project_folder),
                }
                # Attach profile metadata if available
                if mode in ("from_retained", "from_uploads"):
                # if mode == "from_retained":
                    chosen_profile = st.session_state.get("retained_profile")
                    if chosen_profile:
                        project["profile"] = chosen_profile
                        project["module_prefix"] = DASHBOARD_PROFILES.get(chosen_profile, {}).get("module_prefix")


                # Attach an id consistent with existing behavior
                projectlist = st.session_state.get("projectlist", [])
                project["id"] = len(projectlist) + 1
                projectlist.append(project)
                st.session_state["projectlist"] = projectlist
                st.session_state["currproject"] = project["name"]

                # Clear retained dir if it was used
                if mode == "from_retained":
                    shutil.rmtree(st.session_state["retained_json_dir"], ignore_errors=True)
                    for k in [
                        "retained_json_dir",
                        "retained_present_files",
                        "retained_profile",
                        "retained_profile_coverage",
                        "retained_allowed_views",
                        "retained_suggested_views",
                    ]:
                        st.session_state.pop(k, None)
                elif mode == "from_uploads":
                    shutil.rmtree(st.session_state["uploaded_json_dir"], ignore_errors=True)
                    for k in [
                        "uploaded_json_dir", "retained_present_files",
                        "retained_profile", "retained_profile_coverage",
                        "retained_allowed_views", "retained_suggested_views",
                    ]:
                        st.session_state.pop(k, None)
                st.session_state["create_dashboard_from_retained"] = False  # reset flag
                st.session_state["create_dashboard_from_uploads"] = False
                st.toast(f"Dashboard **{project['name']}** created.")
                st.rerun()

    if mode == "crud_dashboard":
        st.markdown("""
            <style>
            .stForm:has(span.red_border_button) .stFormSubmitButton button {
                border: 1px solid rgba(255, 43, 43, 0.5);
            }
            .stForm:has(span.red_border_button) .stFormSubmitButton button:hover {
                border: none;
                background-color: rgba(255, 43, 43, 0.7);
                color: #fff
            }
            </style>
        """, unsafe_allow_html=True)
        currproject = st.session_state['currproject']
        projectlist = st.session_state['projectlist']
        details = [p for p in projectlist if p['name'] == currproject][0]
        index = projectlist.index(details)

        # Remove "Home Page" from the options to avoid mutation of default tab
        current_views = [v for v in details["views"] if v != "Home Page"]

        st.write("Edit project details")

        with st.form("edit_proj_form"):
            st.markdown("<span class='red_border_button'></span>", unsafe_allow_html=True)
            name = st.text_input("Project Name", value=details['name'], key="edit_project_name")
            description = st.text_area("Description", value=details['description'], key="edit_project_description")
            views = st.multiselect(
                "Select Views", 
                options=VIEW_OPTIONS,
                default=current_views,
                key="edit_project_views")

            submitted = st.form_submit_button("Save Project", icon="✅", use_container_width=True)
            if submitted:
                if name == "":
                    st.write("❗ :red[Name cannot be empty]")
                    st.stop()
                
                # 🚫 Duplicate‑name guard (exclude the record being edited)
                if any(
                    (i != index) and (p["name"].lower() == name.lower())
                    for i, p in enumerate(projectlist)
                ):
                    st.error(f"Another project is already named **{name}**.")
                    st.stop()
                
                old_folder = details["folder"]
                new_folder = os.path.join(REPORTS_ROOT, name.lower().replace(" ", "_"))

                if old_folder != new_folder:
                    shutil.move(old_folder, new_folder)            # rename directory

                projectlist[index] = {
                    'id': details['id'], 
                    'name': name, 
                    'description': description, 
                    'views': ["Home Page"] + views, 
                    'folder': new_folder,
                }
                st.session_state['projectlist'] = projectlist
                st.session_state["currproject"] = name

                # Rerun to display the new dashboard immediately
                st.rerun()
        
        with st.expander(":red[Delete this Project?]", icon="🗑️"):
            with st.form("delete_proj_form"):
                retype_proj_name = st.text_input(f"Type the project name **{details['name']}** to confirm deletion")
                if st.form_submit_button("Delete Project", type='primary'):
                    if not retype_proj_name:
                        st.error("Please type the project name to confirm deletion.")
                        st.stop()
                    if retype_proj_name == details['name']:
                        shutil.rmtree(details['folder'], ignore_errors=True)  # delete project folder
                        
                        # Remove the project from the list
                        projectlist.pop(index)
                        # Rearrange index of remaining projects
                        [proj.update({'id': i+1}) for i, proj in enumerate(projectlist)]
                        st.session_state['projectlist'] = projectlist
                        # first prokect in the list or None if empty
                        st.session_state["currproject"] = projectlist[0]['name'] if projectlist != [] else None
                        st.toast(f"Project **{details['name']}** deleted.")
                        st.rerun()
                    elif retype_proj_name != details['name']:
                        st.error(f"Project name does not match.") 
                    

    
    # -------------------- EXISTING BLANK CREATION (unchanged) --------------------
    if mode == 1 or mode == "new_blank":
        # (Keep your current, unmodified 'mode == 1' code block here)
        # BEGIN: existing code
        st.write("Fill in the new dashboard details. **'Home Page' view is always included.**")
        st.caption("*Fields marked **(:red[*])** are required*")
        with st.form("new_proj_form"):
            name = st.text_input("Project (Dashboard) Name **:red[*]**", key="project_name")
            description = st.text_area("Project Description", key="project_description")
            views = st.multiselect("Select additional views to include", VIEW_OPTIONS, key="project_views")

            submitted = st.form_submit_button("Create Project")
            if submitted:
                # prevent duplicate display names (preserving your original logic)
                projectlist = st.session_state.get('projectlist', [])
                if any(p['name'].lower() == name.lower() for p in projectlist):
                    st.error(f"A project called **{name}** already exists. Pick another name.")
                    st.stop()

                project_folder = os.path.join(REPORTS_ROOT, name.lower().replace(" ", "_"))
                os.makedirs(project_folder, exist_ok=True)

                projectlist.append({
                    'id': len(projectlist)+1,
                    'name': name,
                    'description': description,
                    'views': ["Home Page"] + views,
                    'folder': project_folder
                })
                st.session_state['projectlist'] = projectlist
                st.session_state["currproject"] = name
                st.rerun()

@st.dialog("Select a tab below and replace its data")
def replace_data(project):
    """
    • Upload required JSON for selected tabs – auto‑converted to CSV
    • De‑select existing files to delete them
    """
    folder = project["folder"]
    tabs = project["views"]

    st.markdown("### Select tab(s) you want to modify")
    sel_tabs = st.multiselect("Tabs", options=[x for x in tabs if x != "Warnings/Issues"])

    # --------------------------------------- current & required filenames
    # req_json = {f"{tie}.json" for tab in sel_tabs for tie in DATA_TIES[tab]}
    req_json = {f"{tie}.json" for tab in sel_tabs for tie in required_files_for_view(tab, project.get("profile"))}
    existing_json = {f for f in os.listdir(folder) if f.endswith(".json")}
    existing_csv  = {f for f in os.listdir(folder) if f.endswith(".csv")}

    # --------------------------------------- DELETE (un‑tick to remove)
    to_keep = st.multiselect(
        "Files already present (de-select a file to delete it from tab's storage)",
        options=sorted(existing_json & req_json),
        default=sorted(existing_json & req_json),
    )
    st.caption(":red[Do not use the deselect option, if you just want to replace a file.]")
    st.caption(":orange[To update an existing file, just upload a new version below]")
    to_delete = (existing_json & req_json) - set(to_keep)
    if to_delete:
        st.warning(f"These files will be **deleted** on save: {', '.join(to_delete)}")

    # --------------------------------------- UPLOAD
    new_files = st.file_uploader(
        "Upload the JSON files listed below",
        type="json", accept_multiple_files=True,
        key=f"uploader_{project['id']}" 
    )

    # ------------- save uploads (JSON + converted CSV)
    uploaded_names = set()                       # keep track of just‑uploaded names
    for f in new_files:
        json_out = f.name.split(".json")[0].strip().translate({ord(ch): None for ch in '0123456789'}).strip() + ".json"
        path_json = os.path.join(folder, json_out)
        with open(path_json, "wb") as out:
            out.write(f.getbuffer())
        csv_out = f.name.split(".json")[0].strip().translate({ord(ch): None for ch in '0123456789'}).strip() + ".csv"
        json_to_csv(json_file_object=f.getvalue(),
                    csv_output_path=os.path.join(folder, csv_out))
        st.success(f"Saved {json_out} converted and saved")
        uploaded_names.add(json_out)
    
    # ------------------- MISSING / COMPLETE STATUS ---------------------------
    # What will remain after this dialog *if* the user clicks "Save Changes"
    future_present = (existing_json - to_delete) | uploaded_names
    missing_files  = sorted(req_json - future_present)

    if sel_tabs:                                 # only show feedback if a tab was chosen
        if missing_files:
            st.warning(f"Missing required files: {', '.join(missing_files)}")
        else:
            st.success("🎉 All required files are present!")

    # ------------- commit deletes
    if st.button("Save Changes"):
        for filename in to_delete:
            for ext in (".json", ".csv"):
                p = os.path.join(folder, filename.replace(".json", ext))
                if os.path.exists(p):
                    os.remove(p)
        st.rerun()

@st.dialog("🔍 OML Reasoning‑Error Inspector")
def error_inspector_form():

    uploaded = st.file_uploader("Upload a *reasoning.xml* file", type=["xml"])
    if uploaded:
        xml_bytes = uploaded.getvalue()
        try:
            tree = ET.parse(io.BytesIO(xml_bytes))
        except ET.ParseError as e:
            st.error(f"XML parsing error: {e}")
            st.stop()

        failures = tree.findall(".//failure")
        if not failures:
            st.success("No <failure> elements found – the file appears clean 🎉")
            st.stop()

        for idx, fail_elem in enumerate(failures, start=1):
            data = parse_failure_block(fail_elem.text or "")
            if not data:
                st.warning(f"Couldn’t interpret failure block #{idx}.")
                continue
            st.subheader(f"Violation")
            st.write(natural_language_message(data), unsafe_allow_html=True)
            st.dataframe(failure_to_dataframe(data), use_container_width=True, hide_index=True)

from omlbuilder import buildoml, sparql_query, SPARQL_DIR, BUILD_DIR
from pathlib import Path
from streamlit_tree_select import tree_select
from utilities import _build_tree, _fetch_file_bytes, _zip_files, _collect_selected_files

@st.dialog("🟪 Build OML file compiled from Violet", width="large")
def build_oml_form():
    """
    Upload a *.oml bundle → run Gradle build in omltemplateproject →
    surface exit‑code, log and convenience download links.
    """

    st.html("<span class='big-dialog'></span>")

    with st.form("upload_oml_form"):
        uploaded_file = st.file_uploader("Upload a *.oml file", type=["oml"])
        submitted = st.form_submit_button("Upload", icon="⬆️")

    if submitted:
        if uploaded_file is None:
            st.warning("Please choose a *.oml file before running the build.")
        
        elif uploaded_file and not uploaded_file.name.endswith(".oml"):
            st.error("You must upload a *.oml file.")
        elif uploaded_file and uploaded_file.name.endswith(".oml"):
            st.session_state.omluploaded = True
            with st.spinner("Please wait while the OML file is being processed…"):
                result = buildoml(uploaded_file)

            # ----------- surface outcome -------------------------------------------
            exit_code = result.get("exit_code", 1)
            log_rel   = result.get("log_path", "")
            log_abs   = (
                Path(__file__).parent.resolve()
                / "omltemplateproject" / "build" / log_rel
            )

            st.session_state.build_code = exit_code
            st.session_state.build_log_path = log_abs
    
    if st.session_state.omluploaded:
        if st.session_state.build_code == 0:
            st.success("✅ Build succeeded")
        else:
            st.error(f"❌ Build failed (exit code {st.session_state.build_code})")

        # ----------- show / download log ---------------------------------------
        if st.session_state.build_log_path.exists():
            log_abs = st.session_state.build_log_path
            log_text = log_abs.read_text(encoding="utf‑8", errors="ignore")
            with st.expander("🔍 View build log"):
                st.code(log_text, language="bash")

        if st.session_state.build_code == 0:
            st.markdown("### 📝 Next Up -> SPARQL Queries")

            # 1️⃣  Ensure the folder exists
            SPARQL_DIR.mkdir(parents=True, exist_ok=True)
            sparql_files = list(SPARQL_DIR.rglob("*.sparql"))

            st.session_state.sparql_present = bool(len(sparql_files))

            # 2️⃣  If empty → let user upload one / many .sparql files
            if not st.session_state.sparql_present:
                st.info("No queries found yet ‑ upload one or more *.sparql files.")
                upload_files = st.file_uploader(
                    "Upload SPARQL file(s)",
                    type=["sparql"],
                    accept_multiple_files=True,
                    key="sparql_uploader",
                )
                # Save immediately so the button can enable in this session
                for uf in upload_files or []:
                    (SPARQL_DIR / uf.name).write_bytes(uf.read())
                # refresh list after save
                sparql_files = list(SPARQL_DIR.glob("*.sparql"))
                st.session_state.sparql_present = bool(len(sparql_files))
            
            # 3️⃣  Show list of queries (if any)
            if st.session_state.sparql_present:
                with st.expander("**Queries that will be executed:**"):
                    for f in sparql_files:
                        st.markdown(f"- `{f.name}`")

            # 4️⃣  Run‑query button (disabled if the folder is still empty)
            run_queries = st.button(
                "🚀 Run SPARQL queries",
                disabled=not st.session_state.sparql_present,
            )

            # 5️⃣  Execute and surface results/logs
            if run_queries:
                with st.spinner("Running SPARQL queries…"):
                    q_result = sparql_query()

                q_exit = q_result.get("exit_code", 1)
                q_log_rel = q_result.get("log_path", "")
                q_log_abs = (SPARQL_DIR.parent / "build" / q_log_rel).resolve()
                st.session_state.query_run_exec = True
                st.session_state.query_code = q_exit
                st.session_state.query_log_path = q_log_abs
                st.session_state.query_results = q_result.get("results", [])

            if st.session_state.query_run_exec:
                if st.session_state.query_code == 0:
                    st.success("✅ Queries completed without errors")
                else:
                    st.error(f"❌ One or more queries failed (exit code {st.session_state.query_code})")

                # read + show query log
                if st.session_state.query_log_path.exists():
                    q_log_abs = st.session_state.query_log_path
                    qlog_text = q_log_abs.read_text(encoding="utf‑8", errors="ignore")
                    with st.expander("🔍 View SPARQL log"):
                        st.code(qlog_text, language="bash")

                if st.session_state.query_code == 0:
                    results = st.session_state.query_results
                    build_results_dir = BUILD_DIR / "results"

                    json_files = [p for p in build_results_dir.rglob("*.json")]
                    if json_files:
                        st.markdown("### 📊 Create a Dashboard from these results")
                        if st.button("Use these results to create a dashboard", type="primary", icon="🧱"):
                            tmp = session_tmp_dir("sparql")
                            for p in json_files:
                                shutil.copy2(p, tmp / p.name)
                            # detect which JSONs are populated and match to profiles
                            present_basenames = discover_populated_json_basenames(tmp)
                            # store present files for UI & debugging
                            st.session_state["retained_present_files"] = sorted(list(present_basenames))
                            # score profiles by coverage
                            profile_scores = match_profile_from_basenames(present_basenames, DASHBOARD_PROFILES)
                            # pick top candidate (best coverage)
                            chosen_profile = None
                            chosen_coverage = 0.0
                            if profile_scores:
                                chosen_profile, chosen_coverage, present_cnt, total_req = profile_scores[0]
                                st.session_state['retained_profile_coverage'] = chosen_coverage
                            else:
                                chosen_profile = None
                            # compute allowed views: views listed in profile AND whose required DATA_TIES are present
                            allowed_views = []
                            suggested_views = []
                            if chosen_profile:
                                required_views = DASHBOARD_PROFILES[chosen_profile].get("views", [])
                                for v in required_views:
                                    required_files = set(required_files_for_view(v, chosen_profile))
                                    # If a view has no declared required files, treat as not allowed (or you can allow by policy)
                                    if required_files and required_files.issubset(set(present_basenames)):
                                        allowed_views.append(v)
                                        suggested_views.append(v)
                                st.session_state["retained_profile"] = chosen_profile
                            else:
                                st.session_state['retained_profile'] = None
                            st.session_state['retained_allowed_views'] = allowed_views
                            st.session_state['retained_suggested_views'] = suggested_views
                            st.session_state['retained_json_dir'] = str(tmp)
                            # Open the common wizard; no duplicate logic
                            st.session_state['create_dashboard_from_retained'] = True
                            st.session_state["create_dashboard_from_uploads"] = False
                            print(allowed_views, suggested_views, chosen_profile, str(tmp))
                            st.rerun() # rerun to close current dialog and open the project creation form
                    else:
                        st.info("No JSON results were generated. Upload or add SPARQL queries and re-run.")

                    # if json_files:
                    #     st.markdown("### 📊 Create a Dashboard from these results")
                    #     if st.button("Use these results to create a dashboard", type="primary", icon="🧱"):
                    #         tmp = session_tmp_dir("sparql")
                    #         for p in json_files:
                    #             shutil.copy2(p, tmp / p.name)
                    #         st.session_state["retained_json_dir"] = str(tmp)
                    #         # Open the common wizard; no duplicate logic
                    #         st.session_state["create_dashboard_from_retained"] = True
                    #         st.rerun() #rerun to close current dialog and open the project creation form
                    # else:
                    #     st.info("No JSON results were generated. Upload or add SPARQL queries and re-run.")
                elif st.session_state.query_code == 1:
                    pass
        elif st.session_state.build_code == 1:
            # show a button to download the reasoning.xml file from the "reports" folder of the BUILD_DIR declared in the omlbuilder and write a message
            reasoning_file_path = BUILD_DIR / "reports" / "reasoning.xml"
            
            if reasoning_file_path.exists():
                st.markdown("### 📝 Download Reasoning XML")
                st.caption(":red[The build failed, but you can download the reasoning.xml and use the Error Inspector for error breakdown.]")
                st.download_button(
                    "⬇️ Download Reasoning XML",
                    data=reasoning_file_path.read_bytes(),
                    file_name="reasoning.xml",
                )
            else:
                st.error("Reasoning XML file not found. Please check the build logs for more details.")

def required_files_for_view(view_name: str, profile_name: str | None = None):
    """
    Return the effective list (or empty list) of required JSON basenames for `view_name`.
    If profile_name is provided and that profile has a 'view_data_ties' mapping that
    contains the view, the profile-specific list is returned. Otherwise fall back to DATA_TIES.
    """
    # 1) If profile overrides exist, prefer them
    if profile_name:
        profile = DASHBOARD_PROFILES.get(profile_name, {})
        profile_ties = profile.get("view_data_ties", {})
        if view_name in profile_ties:
            return list(profile_ties.get(view_name) or [])
    # 2) Fall back to the global DATA_TIES
    return list(DATA_TIES.get(view_name, []))

@st.dialog("New project from JSON files")
def new_project_from_json_form():
    """Upload SPARQL JSON files, stage them in a temp dir, and reuse project_form(mode='from_uploads')."""
    st.markdown("**Step 1 of 2** — Upload the SPARQL JSON results that will power your dashboard.")
    uploaded = st.file_uploader(
        "Upload one or more .json files",
        type=["json"],
        accept_multiple_files=True,
        key="json_uploads",
        help="Tip: These are the JSON files produced by your SPARQL step (e.g., Requirements.json, TestFacilities.json).",
    )
    if uploaded:
        with st.expander("Files selected", expanded=False):
            for f in uploaded:
                st.markdown(f"• {f.name}")

    cols = st.columns([1,1,2])
    with cols[0]:
        cancel = st.button("Cancel", type="secondary")
    with cols[1]:
        cont = st.button("Continue", type="primary", disabled=not uploaded)

    if cancel:
        st.rerun()

    if cont and uploaded:
        tmp = session_tmp_dir("json_uploads")
        for uf in uploaded:
            # Write each uploaded file into the temp dir as-is
            (tmp / uf.name).write_bytes(uf.read())
        
        # detect which JSONs are populated and match to profiles
        present_basenames = discover_populated_json_basenames(tmp)
        # store present files for UI & debugging
        st.session_state["retained_present_files"] = sorted(list(present_basenames))
        # score profiles by coverage
        profile_scores = match_profile_from_basenames(present_basenames, DASHBOARD_PROFILES)
        # pick top candidate (best coverage)
        chosen_profile = None
        chosen_coverage = 0.0
        if profile_scores:
            chosen_profile, chosen_coverage, present_cnt, total_req = profile_scores[0]
            st.session_state['retained_profile_coverage'] = chosen_coverage
        else:
            chosen_profile = None
        # compute allowed views: views listed in profile AND whose required DATA_TIES are present
        allowed_views = []
        suggested_views = []
        if chosen_profile:
            required_views = DASHBOARD_PROFILES[chosen_profile].get("views", [])
            for v in required_views:
                required_files = set(required_files_for_view(v, chosen_profile))
                # If a view has no declared required files, treat as not allowed (or you can allow by policy)
                if required_files and required_files.issubset(set(present_basenames)):
                    allowed_views.append(v)
                    suggested_views.append(v)
            st.session_state["retained_profile"] = chosen_profile
        else:
            st.session_state['retained_profile'] = None
        st.session_state['retained_allowed_views'] = allowed_views
        st.session_state['retained_suggested_views'] = suggested_views
        st.session_state["uploaded_json_dir"] = str(tmp)

        # Launch the unified creation wizard (single source of truth)
        # project_form(mode="from_uploads", json_dir=str(tmp))
        st.session_state['create_dashboard_from_uploads'] = True
        st.session_state["create_dashboard_from_retained"] = False
        st.rerun() # rerun to close current dialog and open the project creation form



# @st.dialog("New project from JSONs")
# def new_project_from_json_form():
#     """
#     Upload SPARQL JSON files, stage them in a temp dir, and reuse project_form(mode='from_uploads').
#     """
#     uploaded = st.file_uploader("Upload one or more SPARQL result JSON files", type=["json"], accept_multiple_files=True, key="json_uploads")
#     if not uploaded:
#         st.caption("Tip: You can upload the files exported by the SPARQL step (e.g., TestFacilities.json, Requirements.json).")
#     continue_clicked = st.button("Continue", type="primary", disabled=not uploaded)

#     if continue_clicked and uploaded:
#         tmp = session_tmp_dir("json_uploads")
#         for uf in uploaded:
#             (tmp / uf.name).write_bytes(uf.read())
#         # Reuse the common wizard (single source of truth)
#         project_form(mode="from_uploads", json_dir=str(tmp))












# DELETED CODE SNIPPETS BELOW (for context)
                    # cols = st.columns(2)
                    # with cols[0]:
                    #     # surface any result files that Gradle placed into build/results
                    #     results = st.session_state.query_results
                    #     build_results_dir = BUILD_DIR / "results"
                    #     all_files = [
                    #         str(p.relative_to(build_results_dir).as_posix())
                    #         for p in build_results_dir.rglob("*")
                    #         if p.is_file()
                    #     ]
                    #     if results:
                    #         st.markdown("### 📁 Query Result Files")
                    #         st.caption(":green[Select files to download them individually or as a ZIP]")
                    #         st.session_state["dir_tree"] = _build_tree(all_files)
                    #         tree_ret = tree_select(
                    #             st.session_state["dir_tree"],
                    #             checked=[],
                    #             expanded=["results"],
                    #             key="sparql_tree_select",
                    #         )
                    #         if tree_ret:
                    #             checked_set = set(tree_ret.get("checked", []))
                    #             st.session_state.sparql_selected_nodes = _collect_selected_files(
                    #                 st.session_state["dir_tree"], checked_set
                    #             )
                    #         else:
                    #             st.session_state.sparql_selected_nodes = []
                    # with cols[1]:
                    #     st.markdown("### ⬇️ Download")
                    #     selected = st.session_state.sparql_selected_nodes
                    #     if selected:
                    #         with st.expander("Selected files"):
                    #             for fp in selected:
                    #                 st.markdown(f"• {fp}")
                    #         # decide MIME for single‑file case
                    #         if len(selected) == 1:
                    #             sel_path = selected[0]
                    #             data = _fetch_file_bytes(build_results_dir, sel_path)
                    #             if data is not None:
                    #                 mime, _ = mimetypes.guess_type(sel_path)
                    #                 st.download_button(
                    #                     label="Download file",
                    #                     data=data,
                    #                     file_name=sel_path,
                    #                     mime=mime or "application/octet-stream",
                    #                     type="primary",
                    #                     icon="📃",
                    #                 )
                    #         else:
                    #             zip_buf = _zip_files(build_results_dir, selected)
                    #             st.download_button(
                    #                 label="Download selected as ZIP",
                    #                 data=zip_buf,
                    #                 file_name="sparql_results_bundle.zip",
                    #                 mime="application/zip",
                    #                 type="primary",
                    #                 icon="📦",
                    #             )