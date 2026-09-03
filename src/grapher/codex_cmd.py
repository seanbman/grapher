"""Codex integration: AGENTS.md, skill, context export/receive."""

from __future__ import annotations

import importlib.resources as resources
import os
import re
from pathlib import Path
from typing import Any

from grapher.codex_ctx import render_context_from_pack, render_context_markdown
from grapher.ingest import project_root_for
from grapher.store import init_store, load_graph, resolve_graph_path
from grapher.transfer import (
    TransferError,
    pack_graph,
    read_pack,
    unpack_graph,
)

MARK_START = "<!-- grapher:codex:start -->"
MARK_END = "<!-- grapher:codex:end -->"
CONTEXT_FILENAME = "GRAPHER_CONTEXT.md"
PACK_FILENAME = "idea.grapherpack.json"


def _read_asset(*parts: str) -> str:
    pkg = resources.files("grapher")
    return pkg.joinpath(*parts).read_text(encoding="utf-8")


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def _project_root(graph: str | None = None) -> tuple[Path, Path]:
    graph_path = resolve_graph_path(graph, create=True)
    return project_root_for(graph_path), graph_path


def upsert_agents_section(agents_path: Path, section: str) -> str:
    section = section.strip() + "\n"
    if not agents_path.is_file():
        agents_path.write_text(section + "\n", encoding="utf-8")
        return "written"
    text = agents_path.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(MARK_START) + r".*?" + re.escape(MARK_END),
        re.DOTALL,
    )
    if pattern.search(text):
        new_text = pattern.sub(section.strip(), text)
        if new_text == text:
            return "unchanged"
        agents_path.write_text(new_text if new_text.endswith("\n") else new_text + "\n", encoding="utf-8")
        return "updated"
    # append
    sep = "" if text.endswith("\n") else "\n"
    agents_path.write_text(text + sep + "\n" + section + "\n", encoding="utf-8")
    return "appended"


def install_codex_skill(*, force: bool = False) -> dict[str, str]:
    skill_text = _read_asset("codex_assets", "skills", "grapher", "SKILL.md")
    dest = _codex_home() / "skills" / "grapher" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and not force:
        if dest.read_text(encoding="utf-8") == skill_text:
            return {"path": str(dest), "status": "unchanged"}
        return {"path": str(dest), "status": "exists"}
    dest.write_text(skill_text, encoding="utf-8")
    return {"path": str(dest), "status": "written"}


def install_codex_integration(
    *,
    graph: str | None = None,
    force: bool = False,
    ensure_init: bool = True,
) -> dict[str, Any]:
    root, graph_path = _project_root(graph)
    if ensure_init:
        init_store(graph_path)
    section = _read_asset("codex_assets", "AGENTS.section.md")
    agents_path = root / "AGENTS.md"
    agents_status = upsert_agents_section(agents_path, section)
    skill = install_codex_skill(force=force)

    ctx_path = graph_path.parent / CONTEXT_FILENAME
    return {
        "action": "codex_install",
        "project_root": str(root),
        "graph": str(graph_path),
        "agents_md": str(agents_path),
        "agents_status": agents_status,
        "skill": skill,
        "context_present": ctx_path.is_file(),
        "context_path": str(ctx_path),
        "ok": True,
        "message": "Codex integration installed (AGENTS.md + ~/.codex/skills/grapher)",
    }


def codex_status(*, graph: str | None = None) -> dict[str, Any]:
    try:
        root, graph_path = _project_root(graph)
        graph_ok = graph_path.is_file()
    except FileNotFoundError:
        root = Path.cwd().resolve()
        graph_path = None
        graph_ok = False

    agents_path = root / "AGENTS.md"
    agents_has = False
    if agents_path.is_file():
        text = agents_path.read_text(encoding="utf-8")
        agents_has = MARK_START in text and MARK_END in text

    skill_path = _codex_home() / "skills" / "grapher" / "SKILL.md"
    ctx_path = (
        (graph_path.parent / CONTEXT_FILENAME)
        if graph_path
        else root / ".grapher" / CONTEXT_FILENAME
    )
    return {
        "action": "codex_status",
        "project_root": str(root),
        "graph": str(graph_path) if graph_path else None,
        "graph_initialized": graph_ok,
        "agents_section": agents_has,
        "agents_path": str(agents_path),
        "skill_installed": skill_path.is_file(),
        "skill_path": str(skill_path),
        "context_present": ctx_path.is_file(),
        "context_path": str(ctx_path),
        "ready": bool(
            graph_ok and agents_has and skill_path.is_file()
        ),
    }


def write_context_file(
    out_path: Path,
    *,
    graph: dict[str, Any] | None = None,
    pack: dict[str, Any] | None = None,
    name: str = "",
    description: str = "",
) -> Path:
    if pack is not None:
        text = render_context_from_pack(pack)
    elif graph is not None:
        text = render_context_markdown(
            graph, name=name or "untitled", description=description
        )
    else:
        raise TransferError("write_context_file requires graph or pack")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def codex_context(
    *,
    graph: str | None = None,
    from_pack: str | None = None,
    output: str | None = None,
    name: str = "",
    description: str = "",
) -> dict[str, Any]:
    if from_pack:
        pack = read_pack(Path(from_pack))
        text = render_context_from_pack(pack)
        meta = pack.get("meta") or {}
        name = name or str(meta.get("name") or "untitled")
        description = description or str(meta.get("description") or "")
        node_count = len((pack.get("graph") or {}).get("nodes") or {})
        edge_count = len((pack.get("graph") or {}).get("edges") or [])
    else:
        _, graph_path = _project_root(graph)
        g = load_graph(graph_path)
        text = render_context_markdown(
            g, name=name or "project", description=description
        )
        node_count = len(g.get("nodes") or {})
        edge_count = len(g.get("edges") or [])

    out_path = None
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")

    return {
        "action": "codex_context",
        "name": name or "untitled",
        "description": description,
        "nodes": node_count,
        "edges": edge_count,
        "path": str(out_path.resolve()) if out_path else None,
        "markdown": text if not output else None,
        "chars": len(text),
    }


def codex_export(
    out_dir: Path,
    *,
    graph: str | None = None,
    name: str = "",
    description: str = "",
    include_vectors: bool = True,
) -> dict[str, Any]:
    root, graph_path = _project_root(graph)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pack_path = out_dir / PACK_FILENAME
    ctx_path = out_dir / CONTEXT_FILENAME
    readme_path = out_dir / "README.md"

    pack_result = pack_graph(
        graph_path,
        pack_path,
        name=name or root.name,
        description=description,
        include_vectors=include_vectors,
    )
    pack = read_pack(pack_path)
    write_context_file(ctx_path, pack=pack)
    readme_path.write_text(
        _read_asset("codex_assets", "transplant_README.md"), encoding="utf-8"
    )
    return {
        "action": "codex_export",
        "directory": str(out_dir.resolve()),
        "pack": str(pack_path.resolve()),
        "context": str(ctx_path.resolve()),
        "readme": str(readme_path.resolve()),
        "name": pack_result.get("name"),
        "description": pack_result.get("description") or "",
        "nodes": pack_result.get("nodes", 0),
        "edges": pack_result.get("edges", 0),
        "vectors": pack_result.get("vectors", 0),
        "message": "Codex transplant kit written — receive with: grapher codex receive <DIR>",
    }


def _resolve_receive_pack(source: Path) -> tuple[Path, Path | None]:
    """Return (pack_path, kit_context_path_or_None)."""
    source = Path(source)
    if source.is_dir():
        pack = source / PACK_FILENAME
        if not pack.is_file():
            # accept any single *.grapherpack.json
            cands = sorted(source.glob("*.grapherpack.json")) + sorted(
                source.glob("*pack*.json")
            )
            cands = [p for p in cands if p.is_file()]
            if not cands:
                raise TransferError(
                    f"no {PACK_FILENAME} (or *grapherpack*.json) in {source}"
                )
            pack = cands[0]
        ctx = source / CONTEXT_FILENAME
        return pack, ctx if ctx.is_file() else None
    if source.is_file():
        return source, None
    raise TransferError(f"receive source not found: {source}")


def codex_receive(
    source: Path,
    *,
    graph: str | None = None,
    mode: str = "merge",
    prefix: str = "",
    include_vectors: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    root, graph_path = _project_root(graph)
    init_store(graph_path)
    pack_path, kit_ctx = _resolve_receive_pack(Path(source))
    unpack_result = unpack_graph(
        graph_path,
        pack_path,
        mode=mode,
        prefix=prefix,
        include_vectors=include_vectors,
    )
    # Prefer kit's pre-rendered context; else render from pack (with prefix applied via live graph)
    dest_ctx = graph_path.parent / CONTEXT_FILENAME
    if kit_ctx and not prefix:
        dest_ctx.write_text(kit_ctx.read_text(encoding="utf-8"), encoding="utf-8")
        ctx_source = "kit"
    else:
        # Render from current graph after unpack so prefix ids match
        g = load_graph(graph_path)
        pack = read_pack(pack_path)
        meta = pack.get("meta") or {}
        write_context_file(
            dest_ctx,
            graph=g,
            name=str(meta.get("name") or unpack_result.get("name") or "transplant"),
            description=str(meta.get("description") or ""),
        )
        ctx_source = "rendered"
    install = install_codex_integration(
        graph=str(graph_path), force=force, ensure_init=False
    )
    return {
        "action": "codex_receive",
        "project_root": str(root),
        "pack": str(pack_path.resolve()),
        "context": str(dest_ctx.resolve()),
        "context_source": ctx_source,
        "unpack": unpack_result,
        "install": {
            "agents_status": install.get("agents_status"),
            "skill": install.get("skill"),
        },
        "message": (
            "Received for Codex. Start Codex here; it should read "
            f"{CONTEXT_FILENAME} fully before acting."
        ),
        "hint": unpack_result.get("hint"),
    }
