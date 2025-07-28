import os, re
import pandas as pd
import streamlit as st

STANDARD_MSG = "{}.json data is not available – upload it via **Edit Data**"

# ────────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ────────────────────────────────────────────────────────────────
def render(project: dict) -> None:
    st.markdown("## Warnings / Issues")
    for section in ("test_strategy", "requirements", "test_results"):
        issuesinfo(project, section)
        st.divider()


# ────────────────────────────────────────────────────────────────
#  DISPLAY
# ────────────────────────────────────────────────────────────────
def issuesinfo(project: dict, section: str) -> None:
    cont = st.container(border=True)
    issues = create_issues(project)[section]

    title = {
        "test_strategy": "Test‑Strategy Checks",
        "requirements":  "Requirements Checks",
        "test_results":  "Test‑Results Checks",
    }[section]
    cont.markdown(f"### {title}")

    if not issues:
        ok = {
            "test_strategy": "No scheduling or resource‑allocation problems detected",
            "requirements":  "No requirement‑level issues detected",
            "test_results":  "No test‑result issues detected",
        }[section]
        cont.success(ok, icon="✅")
        return

    for iss in issues:
        if iss["type"] == "warning":
            cont.warning(iss["message"], icon="⚠️")
        else:
            cont.error(iss["message"], icon="❗")


# ────────────────────────────────────────────────────────────────
#  CORE LOGIC
# ────────────────────────────────────────────────────────────────
def create_issues(project: dict) -> dict:
    folder = project["folder"]
    p      = lambda f: os.path.join(folder, f)

    # Attempt to load all needed CSVs; if any missing we skip those checks.
    try:
        strategy_df  = pd.read_csv(p("TestStrategy.csv"))
    except FileNotFoundError:
        return {"test_strategy": [], "requirements": [], "test_results": []}

    # Normalise column names
    strategy_df.columns = (
        strategy_df.columns.str.replace(r"\s{2,}", " ", regex=True)
                           .str.replace(r"(?<!^)(?=[A-Z])", " ", regex=True)
                           .str.strip()
                           .str.replace("Org$", "Organization", regex=True)
    )

    # ------------------------------------------------------------------ #
    # 1)  TEST‑STRATEGY‑LEVEL ISSUES
    # ------------------------------------------------------------------ #
    ts_issues = []

    # ---- A. total duration > 60 days ---------------------------------
    strategy_df["Duration Value"] = pd.to_numeric(strategy_df["Duration Value"], errors="coerce")
    dur_sum = strategy_df.groupby("Test Case")["Duration Value"].max().sum()

    # add 6 days per facility change
    link = strategy_df[["Test Case", "Occurs Before"]].dropna()
    parent = dict(zip(link["Test Case"], link["Occurs Before"]))
    head = (set(parent.keys()) - set(parent.values())).pop()
    ordered = []
    while head:
        ordered.append(head)
        head = parent.get(head)
    fac_seq = strategy_df.set_index("Test Case").loc[ordered, "Facility"].tolist()
    dur_sum += sum(a != b for a, b in zip(fac_seq[:-1], fac_seq[1:])) * 6

    if dur_sum > 60:
        ts_issues.append(
            {"type": "warning", "message": f"Total campaign duration is {int(dur_sum)} days (> 60)"}
        )

    # ---- B. researcher / equipment availability ----------------------
    # Load facility resources
    equip_map, pers_map = {}, {}
    try:
        eq_df = pd.read_csv(p("TestEquipment.csv"))
        eq_df.columns = eq_df.columns.str.replace(r"(?<!^)(?=[A-Z])", " ", regex=True).str.strip()
        equip_map = eq_df.groupby("Located At")["Equipment"].apply(set).to_dict()
    except FileNotFoundError:
        pass

    try:
        per_df = pd.read_csv(p("TestPersonnel.csv"))
        per_df.columns = per_df.columns.str.replace(r"(?<!^)(?=[A-Z])", " ", regex=True).str.strip()
        pers_map = per_df.groupby("Located At")["Person"].apply(set).to_dict()
    except FileNotFoundError:
        pass

    for _, row in strategy_df.iterrows():
        tc, fac = row["Test Case"], row["Facility"]

        # researcher availability
        researcher = row.get("Researcher")
        if pd.notna(researcher) and fac in pers_map and researcher not in pers_map[fac]:
            ts_issues.append(
                {"type": "error",
                 "message": f"Researcher {researcher} for Test Case {tc} is not available at Facility {fac}"}
            )

        # equipment availability  (column may be absent or NaN)
        eq_val = row.get("Test Equipment")
        if pd.notna(eq_val) and fac in equip_map:
            # allow comma / semicolon separated lists
            for eq in re.split(r"[;,]\s*|\s+", str(eq_val).strip()):
                if eq and eq not in equip_map[fac]:
                    ts_issues.append(
                        {"type": "error",
                         "message": f"Equipment {eq} for Test Case {tc} is not available at Facility {fac}"}
                    )

    ts_issues = pd.DataFrame(ts_issues).drop_duplicates().to_dict('records')
    # issues["requirements"] = pd.DataFrame(issues["requirements"]).drop_duplicates().to_dict('records')
    # issues["test_results"] = pd.DataFrame(issues["test_results"]).drop_duplicates().to_dict('records')


    # ------------------------------------------------------------------ #
    #  (requirements & test‑results checks removed for now)
    # ------------------------------------------------------------------ #
    return {"test_strategy": ts_issues, "requirements": [], "test_results": []}

