import io, zipfile, mimetypes
from pathlib import Path

# for build tools configuration
import os, tarfile, shutil, urllib.request, subprocess
import streamlit as st
import re


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
# GRADLE_URL = "https://services.gradle.org/distributions/gradle-8.14.2-bin.zip"
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

# @st.cache_resource(show_spinner=False)
def ensure_build_tools():
    """
    Download & install JDK‑21 in Debian stable (bookworm) IF:
    • They’re missing, AND
    • We are inside Streamlit Cloud.
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