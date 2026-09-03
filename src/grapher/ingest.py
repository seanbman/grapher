"""Directory scan / ingest helpers for LLM-driven graphing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from grapher.model import slugify

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".grapher",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        ".cursor",
    }
)

IMAGE_EXTS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tif", ".tiff"}
)

VIDEO_EXTS = frozenset(
    {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".wmv", ".flv"}
)

AUDIO_EXTS = frozenset(
    {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".aiff"}
)

DOC_EXTS = frozenset(
    {
        ".md",
        ".txt",
        ".rst",
        ".pdf",
        ".doc",
        ".docx",
        ".rtf",
        ".csv",
        ".tsv",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".xml",
        ".html",
        ".htm",
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".proto",
        ".graphql",
        ".css",
        ".scss",
        ".vue",
        ".svelte",
        ".ipynb",
    }
)


def project_root_for(graph_path: Path) -> Path:
    # .../project/.grapher/knowledge.json -> project
    if graph_path.parent.name == ".grapher":
        return graph_path.parent.parent
    return graph_path.parent


def rel_path(path: Path, root: Path, *, ingest_root: Path | None = None) -> str:
    """Prefer path relative to project root; otherwise absolute (stable matching)."""
    del ingest_root  # reserved for callers; do not store ingest-relative paths
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def path_index(graph: dict[str, Any], project_root: Path) -> dict[str, dict[str, Any]]:
    """Map normalized path keys -> node (relative and absolute forms)."""
    out: dict[str, dict[str, Any]] = {}

    def add_key(key: str, node: dict[str, Any]) -> None:
        out[key] = node
        out[Path(key).as_posix()] = node

    for node in graph["nodes"].values():
        p = node.get("path")
        if not p:
            continue
        add_key(str(p), node)
        pp = Path(p)
        if pp.is_absolute():
            add_key(pp.resolve().as_posix(), node)
        else:
            abs_p = (project_root / pp).resolve()
            add_key(abs_p.as_posix(), node)
            add_key(str(abs_p), node)
    return out


def classify_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in DOC_EXTS:
        return "document"
    return "other"


def iter_files(
    directory: Path,
    *,
    glob: str | None = None,
    max_files: int = 5000,
) -> list[Path]:
    root = directory.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"not a directory: {directory}")

    files: list[Path] = []
    if glob:
        candidates = sorted(root.rglob(glob))
    else:
        candidates = sorted(p for p in root.rglob("*") if p.is_file())

    for p in candidates:
        if not p.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        files.append(p)
        if len(files) >= max_files:
            break
    return files


def file_status(node: dict[str, Any] | None) -> str:
    if node is None:
        return "new"
    meta = node.get("meta") or {}
    if meta.get("status") == "pending" or not (node.get("content") or "").strip():
        return "pending"
    return "indexed"


def stable_path_id(rel: str, node_type: str) -> str:
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]
    base = slugify(Path(rel).stem)[:32]
    return f"{node_type}-{base}-{digest}"


def scan_directory(
    graph: dict[str, Any],
    directory: Path,
    *,
    graph_path: Path,
    glob: str | None = None,
    types: set[str] | None = None,
    max_files: int = 5000,
) -> dict[str, Any]:
    root = project_root_for(graph_path)
    ingest_root = directory.resolve()
    index = path_index(graph, root)
    entries: list[dict[str, Any]] = []
    counts = {"new": 0, "pending": 0, "indexed": 0, "skipped_other": 0}

    for path in iter_files(directory, glob=glob, max_files=max_files):
        ntype = classify_file(path)
        if types and ntype not in types:
            if ntype == "other":
                counts["skipped_other"] += 1
            continue
        if ntype == "other" and not types:
            counts["skipped_other"] += 1
            continue

        stored = rel_path(path, root, ingest_root=ingest_root)
        abs_key = path.resolve().as_posix()
        node = (
            index.get(stored)
            or index.get(abs_key)
            or index.get(str(path.resolve()))
        )
        status = file_status(node)
        counts[status] = counts.get(status, 0) + 1
        entry: dict[str, Any] = {
            "path": stored if node is None else (node.get("path") or stored),
            "abs_path": abs_key,
            "type": ntype,
            "status": status,
            "title": path.name,
        }
        if node:
            entry["node_id"] = node["id"]
            entry["title"] = node.get("title") or path.name
            entry["path"] = node.get("path") or stored
        else:
            entry["path"] = stored
        entries.append(entry)

    return {
        "directory": str(directory.resolve()),
        "project_root": str(root),
        "counts": counts,
        "files": entries,
    }


def ingest_directory(
    graph: dict[str, Any],
    directory: Path,
    *,
    graph_path: Path,
    glob: str | None = None,
    types: set[str] | None = None,
    max_files: int = 5000,
    create_stubs: bool = True,
) -> dict[str, Any]:
    """Create pending stub nodes for new files; return work queue for the LLM."""
    from grapher.graph import add_node

    scanned = scan_directory(
        graph,
        directory,
        graph_path=graph_path,
        glob=glob,
        types=types,
        max_files=max_files,
    )
    created: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    for entry in scanned["files"]:
        if entry["status"] == "indexed":
            continue
        if entry["status"] == "new" and create_stubs:
            node = add_node(
                graph,
                type=entry["type"],
                title=entry["title"],
                content="",
                path=entry["path"],
                tags=["ingest"],
                meta={"status": "pending", "source": "ingest"},
                id=stable_path_id(entry["path"], entry["type"]),
            )
            entry = {
                **entry,
                "status": "pending",
                "node_id": node["id"],
                "created": True,
            }
            created.append(entry)
        if entry["status"] in {"pending", "new"}:
            pending.append(entry)

    return {
        "directory": scanned["directory"],
        "project_root": scanned["project_root"],
        "created_stubs": len(created),
        "pending_count": len(pending),
        "indexed_skipped": scanned["counts"].get("indexed", 0),
        "pending": pending,
        "instruction": (
            "FULL INGEST REQUIRED. Cursor is the enriching LLM — grapher only "
            "stores paths and your written understanding. NEVER graph media as "
            "path-only stubs. For EVERY pending document, image, video, and "
            "audio file: deeply consume it (vision for images/video frames; "
            "listen/transcribe/describe audio), understand it in project "
            "context, then write that deep understanding into --content. "
            "grapher add --id <node_id> --type <type> --title <title> "
            "--path <path> --content <deep summary> --tags ... "
            "Use the exact path from the pending entry. Finish only when "
            "grapher scan <DIR> shows pending 0."
        ),
    }
