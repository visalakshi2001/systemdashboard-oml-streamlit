import io, zipfile, mimetypes
from pathlib import Path


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