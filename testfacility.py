import os
import streamlit as st
import pandas as pd

STANDARD_MSG = "{}.json data is not available – upload it via **Edit Data**"

def render(project: dict) -> None:
    """
    Dynamic Test‑Facilities tab.

    • Reads:
        - TestFacilities.csv     (list of facility names / metadata)
        - TestEquipment.csv      (mapping facility → equipment)
        - TestPersonnel.csv      (mapping facility → researcher / staff)
    • Shows a 2‑column grid; additional rows appear automatically.
    • For each facility: equipment table + bullet list of researchers.
    """

    folder = project["folder"]
    files_needed = {
        "TestFacilities": os.path.join(folder, "TestFacilities.csv"),
        "TestEquipment":  os.path.join(folder, "TestEquipment.csv"),
        "TestPersonnel":  os.path.join(folder, "TestPersonnel.csv"),
    }

    missing = [name for name, path in files_needed.items() if not os.path.exists(path)]
    if missing:
        st.info(", ".join(f"{m}.json" for m in missing) +
                " data is not available – upload it via **Edit Data**")
        return

    facilities_df = pd.read_csv(files_needed["TestFacilities"])
    equipment_df  = pd.read_csv(files_needed["TestEquipment"])
    personnel_df  = pd.read_csv(files_needed["TestPersonnel"])

    # Normalise column names once
    facilities_df.columns = facilities_df.columns.str.replace(
        r"(?<!^)(?=[A-Z])", " ", regex=True).str.strip()
    equipment_df.columns  = equipment_df.columns.str.replace(
        r"(?<!^)(?=[A-Z])", " ", regex=True).str.strip()
    personnel_df.columns  = personnel_df.columns.str.replace(
        r"(?<!^)(?=[A-Z])", " ", regex=True).str.strip()

    # Ensure we have the key columns we expect
    fac_col = "Test Facility"
    eq_col  = "Equipment"
    per_col = "Person"
    fac_loc_col = "Located At"

    facilities = facilities_df[fac_col].unique()

    # Build 2‑column layout
    for i in range(0, len(facilities), 2):
        cols = st.columns(2)
        for idx, fac in enumerate(facilities[i : i + 2]):
            with cols[idx]:
                pretty = fac.replace("_", " ")
                st.subheader(f"🏭 {pretty}", divider="orange")

                # ---- Equipment table ---------------------------------------
                equip_list = (
                    equipment_df[equipment_df[fac_loc_col] == fac][eq_col]
                    .dropna()
                    .value_counts()
                    .rename_axis("Equipment")
                    .reset_index(name="Count")
                )
                st.markdown("**Available Equipment**")
                if equip_list.empty:
                    st.info("No equipment registered for this facility.")
                else:
                    st.dataframe(equip_list, hide_index=True, use_container_width=True)

                # ---- Personnel list ----------------------------------------
                pers = (
                    personnel_df[personnel_df[fac_loc_col] == fac][per_col]
                    .dropna()
                    .unique()
                )
                st.markdown("**Researchers / Personnel**")
                if len(pers) == 0:
                    st.info("No personnel registered for this facility.")
                else:
                    st.markdown("\n".join(f"- {p}" for p in pers))
