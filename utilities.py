import io, zipfile, mimetypes
from pathlib import Path

# for build tools configuration
import os, tarfile, shutil, urllib.request, subprocess
import streamlit as st
import re

import logging
# Basic configuration for logging to the console
# logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')

# Get a logger instance
logger = logging.getLogger()

REPORTS_ROOT = "reports"

def _fetch_file_bytes(base_dir: Path, rel_path: str) -> bytes | None:
    """Return raw bytes of a result file inside `base_dir` or None if missing."""
    fpath = (base_dir / rel_path).resolve()
    if fpath.exists() and fpath.is_file():
        return fpath.read_bytes()
    return None


def _zip_files(base_dir: Path, rel_paths: list[str]) -> bytes:
    """Return an in‑memory ZIP of the selected result files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in rel_paths:
            fpath = (base_dir / rel).resolve()
            if fpath.exists() and fpath.is_file():
                zf.writestr(rel, fpath.read_bytes())
    buf.seek(0)
    return buf.getvalue()

def _build_tree(paths: list[str]) -> list[dict]:
    """
    Turn ['dir1/a.json','dir1/b.json','dir2/c.ttl'] into the nested structure
    expected by streamlit_tree_select.
    """
    root: dict[str, dict] = {}
    for p in paths:
        parts = p.split("/")
        cur = root
        for idx, part in enumerate(parts):
            if part not in cur:
                cur[part] = {} if idx < len(parts) - 1 else None
            if cur[part] is not None:
                cur = cur[part]
    # recursive conversion
    def to_nodes(d: dict | None, name: str = "") -> dict:
        if d is None:
            return {"label": name, "value": name}
        return {
            "label": name or "results",
            "value": name or "results",
            "children": [to_nodes(v, k) for k, v in sorted(d.items())],
        }
    return [to_nodes(root)]

def _collect_all_file_keys(node):
    """Return all descendant file keys under *node*."""
    if "children" in node and node["children"]:
        files = []
        for child in node["children"]:
            files.extend(_collect_all_file_keys(child))
        return files
    # leaf → file node
    return [node["value"]]

def _collect_selected_files(tree, checked):
    """Expand folder selections into their contained files; return unique list."""
    selected_files = []

    def _traverse(nodes):
        for n in nodes:
            if n["value"] in checked:
                selected_files.extend(_collect_all_file_keys(n))
            elif "children" in n:
                _traverse(n["children"])

    _traverse(tree)
    # de‑duplicate while preserving order
    seen = set()
    uniq_ordered = [f for f in selected_files if not (f in seen or seen.add(f))]
    return uniq_ordered



# --------------------------------------------------------------------------- #
# ⬇️  Config
JDK_URL = (
    "https://download.java.net/java/GA/jdk21.0.2/"
    "f2283984656d49d69e91c558476027ac/13/GPL/openjdk-21.0.2_linux-x64_bin.tar.gz"
)
# --------------------------------------------------------------------------- #

def _has_tool(cmd: str, pattern: str | None = None) -> bool:
    """Return True if `cmd` exists and (optionally) its version matches `pattern`."""
    try:
        out = subprocess.check_output([cmd, "--version"], stderr=subprocess.STDOUT)
        if pattern:
            return bool(re.search(pattern.encode(), out))
        return True
    except Exception:
        return False


def _running_on_streamlit_cloud() -> bool:          # ⭐ NEW
    """
    Streamlit Cloud sets a handful of env‑vars (most notably ST_FILESYSTEM_ROOT).
    Checking one that is unlikely to be set elsewhere keeps the test cheap.
    """
    return os.environ['HOSTNAME'] == 'streamlit'

@st.cache_resource(show_spinner=True)
def ensure_build_tools():
    """
    Download & install JDK‑21 in Debian stable (bookworm) IF:
    • They’re missing, AND
    • We are inside Streamlit Cloud.

    Thanks to "https://green.cloud/docs/how-to-install-java-jdk-21-or-openjdk-21-on-debian-12/"

    """
    # 1️⃣  Short‑circuit for local dev / already‑setup boxes
    java_ok = _has_tool("java", r"build 21\.")

    if java_ok:
        return                          # nothing to do

    if not _running_on_streamlit_cloud():              # ⭐ NEW
        # Don’t mutate the local machine; just raise a helpful error.
        st.error(
            "Java 21 and/or Gradle not found on PATH.\n"
            "Install them locally or run this app on Streamlit Cloud."
        )
        st.stop()

    # 2️⃣  Cloud bootstrap (same logic as before) ----------------------------
    home = Path.home()
    
    # -------- JDK -----------------------------------------------------------
    jdk_root = home / ".jdk21"
    java_bin = jdk_root / "bin" / "java"
    if not java_bin.exists():
        tgz = home / "jdk21.tar.gz"
        urllib.request.urlretrieve(JDK_URL, tgz)
        jdk_root.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tgz, "r:gz") as t:
            t.extractall(path=jdk_root)
        inner = next(jdk_root.glob("jdk-*"))
        for item in inner.iterdir():
            shutil.move(str(item), jdk_root)
        inner.rmdir()
    os.environ["JAVA_HOME"] = str(jdk_root)
    os.environ["PATH"] = f"{jdk_root}/bin:" + os.environ["PATH"]

    # -------- sanity check --------------------------------------------------
    try:
        subprocess.run(["java", "-version"], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        st.error("Java bootstrap failed:\n" + e.stderr.decode())
        st.stop()

def _run_installation_if_streamlit_env():
    """
    Check if the current OS is Debian-based and is Streamlit.
    """
    if os.name == "posix":
        ensure_build_tools()
    return



import uuid
import json

def session_tmp_dir(kind: str) -> Path:
    """
    Create a unique temp directory under ./.tmp for the current session.
    Returns a Path to the created directory.
    """
    base = Path(REPORTS_ROOT) / Path(".tmp")
    base.mkdir(parents=True, exist_ok=True)
    d = base / f"{kind}_{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    return d

def discover_json_basenames(src: Path) -> list[str]:
    """
    Return sorted unique basenames (without .json) for all JSON files in src (recursive).
    """
    src = Path(src)
    basenames = set()
    for p in src.rglob("*.json"):
        basenames.add(p.stem)
    return sorted(basenames)

def suggest_tabs_from_json(basenames: list[str], DATA_TIES: dict) -> list[str]:
    """
    Given JSON basenames and DATA_TIES (tab -> required basenames),
    return tabs whose required basenames are ALL present.
    Excludes 'Home Page' (which is always included by the app).
    """
    suggestions = []
    for tab, needs in DATA_TIES.items():
        if tab == "Home Page":
            continue
        if all(n in basenames for n in needs):
            suggestions.append(tab)
    # Return in stable alpha order
    return sorted(suggestions)


def discover_populated_json_basenames(src):
    """
    Walk `src` recursively, open each *.json, and return a set of basenames
    (file stem, no extension) for JSON files that appear *populated*.

    Heuristic used: JSON has a top-level "results" -> "bindings" list with len > 0.
    This matches the SPARQL JSON shape you showed:

      { "head": { ... }, "results": { "bindings": [ ... ] } }

    Files that fail to parse are skipped.
    """
    src = Path(src)
    present = set()
    for p in src.rglob("*.json"):
        try:
            raw = p.read_text(encoding="utf-8")
            j = json.loads(raw)
        except Exception:
            # skip unreadable/bad json
            continue

        # Common SPARQL JSON shape: results.bindings -> list
        bindings = j.get("results", {}).get("bindings", None)
        if isinstance(bindings, list) and len(bindings) > 0:
            present.add(p.stem)
            continue

        # Some queries might return boolean or other output; treat truthy values as populated
        # e.g. {"boolean": true}
        if j.get("boolean") is True:
            present.add(p.stem)
            continue

        # (If you have other shapes to consider, we can add them here.)
    print("present base names with length > 0:", present)
    logger.debug(f"{src}present base names with length > 0:{present}")
    return present


def match_profile_from_basenames(present_basenames,profiles):
    """
    Given a set of present JSON basenames and a profiles dict of the form:
      { profile_name: {"data": [...], "views": [...], "module_prefix": "..."} }

    Return a list of tuples:
      (profile_name, coverage_fraction, present_count, total_required)

    Sorted in descending order by coverage_fraction, then by present_count.
    Coverage fraction = present_count / total_required (0..1).
    """
    scored = []
    for name, info in profiles.items():
        required = set(info.get("data", []))
        total = max(1, len(required))
        present_count = len(required & set(present_basenames))
        coverage = present_count / total
        scored.append((name, coverage, present_count, total))
    # sort: highest coverage first, then most present files
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
    print("profile coverage scores:", scored)
    logger.debug(f"profile coverage scores: {scored}")
    return scored


def view_name_to_module_name(view_name):
    """
    Convert a human view name to a compact module identifier suitable for imports.

    Examples:
      "Test Strategy" -> "teststrategy"
      "Requirements / Sys" -> "requirementssys"
    (Removes non-alnum characters and lowercases.)
    """
    # remove non-alphanumeric, convert spaces to nothing, lowercase
    s = view_name.lower().replace(" ", "")
    # drop any remaining non-alphanumeric/underscore characters
    s = re.sub(r"[^0-9a-z_]", "", s)
    # ensure it doesn't start with digit (module names shouldn't)
    if re.match(r"^\d", s):
        s = "_" + s
    return s
# --------------------------------------------------------------------------- #

# def _slugify_name(name: str) -> str:
#     # simple slug consistent with existing code: lower, spaces -> underscores
#     return name.lower().strip().replace(" ", "_")

# def _unique_folder(base: Path) -> Path:
#     """
#     If 'base' exists, suffix with -2, -3, ... until unique.
#     """
#     if not base.exists():
#         return base
#     n = 2
#     while True:
#         cand = base.parent / f"{base.name}-{n}"
#         if not cand.exists():
#             return cand
#         n += 1

# def materialize_dashboard(
#     *,
#     name: str,
#     description: str,
#     tabs: list[str],
#     json_src_dir: Path,
#     DATA_TIES: dict,
#     reports_root: str | Path = "reports",
# ):
#     """
#     Create dashboard folder under reports_root/name, copy JSONs from json_src_dir,
#     convert JSON->CSV for every JSON present, and return:
#       (project_dict, project_folder_path, final_display_name)

#     project_dict matches the shape used in projectdetail.project_form(mode=1).
#     """
#     from jsontocsv import json_to_csv  # local import to avoid circulars

#     # 1) Create project folder
#     reports_root = Path(reports_root)
#     reports_root.mkdir(exist_ok=True)
#     target = reports_root / _slugify_name(name)
#     target = _unique_folder(target)
#     target.mkdir(parents=True, exist_ok=True)

#     # If final name changed due to uniqueness, reflect in display name
#     final_display_name = name if target.name == _slugify_name(name) else target.name.replace("_", " ").title()

#     # 2) Copy all JSONs (flat copy is sufficient; keep filenames)
#     src = Path(json_src_dir)
#     copied = []
#     for p in src.rglob("*.json"):
#         dest = target / p.name
#         shutil.copy2(p, dest)
#         copied.append(dest)

#     # 3) Convert each JSON -> CSV beside it
#     for dest in copied:
#         csv_out = dest.with_suffix(".csv")
#         try:
#             json_to_csv(csv_output_path=str(csv_out), json_input_path=str(dest))
#         except Exception as e:
#             # Do not fail the whole materialization if one file is bad
#             print(f"[materialize_dashboard] Failed to convert {dest.name}: {e}")

#     # 4) Build project dict (Home Page always included)
#     project = {
#         "id": None,  # filled by caller to keep existing numbering logic, if needed
#         "name": final_display_name,
#         "description": description,
#         "views": ["Home Page"] + list(tabs),
#         "folder": str(target),
#     }
#     return project, target, final_display_name