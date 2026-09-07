"""Load/save knowledge graph and vector sidecar; resolve project paths."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from grapher.config import default_config, load_config, save_config
from grapher.model import empty_graph, empty_vectors, normalize_graph

GRAPH_DIRNAME = ".grapher"
GRAPH_FILENAME = "knowledge.json"
VECTORS_FILENAME = "vectors.json"


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".grapher-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def find_graph_dir(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        graph_file = candidate / GRAPH_DIRNAME / GRAPH_FILENAME
        if graph_file.is_file():
            return candidate / GRAPH_DIRNAME
    return None


def resolve_graph_path(
    explicit: str | None = None,
    *,
    create: bool = False,
) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("GRAPHER_GRAPH")
    if env:
        return Path(env).expanduser().resolve()
    found = find_graph_dir()
    if found:
        return found / GRAPH_FILENAME
    if create:
        return (Path.cwd() / GRAPH_DIRNAME / GRAPH_FILENAME).resolve()
    raise FileNotFoundError(
        "no knowledge graph found; run `grapher init` or pass --graph"
    )


def vectors_path_for(graph_path: Path) -> Path:
    return graph_path.parent / VECTORS_FILENAME


def load_graph(path: Path, *, normalize: bool = True) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"graph not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("graph file must be a JSON object")
    data.setdefault("version", 1)
    data.setdefault("nodes", {})
    data.setdefault("edges", [])
    if normalize:
        data = normalize_graph(data)
        # Any record that already carries a semantic seal must verify on read.
        # Legacy finalized records without a seal remain readable until their
        # next canonical write bootstraps the new integrity scheme.
        from grapher.integrity import verify_node_integrity

        for node_id, node in (data.get("nodes") or {}).items():
            if not node.get("integrity"):
                continue
            check = verify_node_integrity(node)
            if not check["valid"]:
                raise ValueError(
                    f"semantic integrity mismatch for node {node_id!r}: {check['reason']}"
                )
    return data


def save_graph(path: Path, data: dict[str, Any]) -> None:
    _atomic_write(path, data)


def history_path_for(graph_path: Path) -> Path:
    return graph_path.parent / "history.jsonl"


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_history(graph_path: Path, entry: dict[str, Any]) -> None:
    history_path = history_path_for(graph_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n"
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _actor_from_context(context: dict[str, Any] | None) -> dict[str, Any] | None:
    provenance = (context or {}).get("provenance") or {}
    actor = {
        "id": provenance.get("actor_id"),
        "kind": provenance.get("actor_kind"),
        "role": provenance.get("actor_role"),
        "session_id": provenance.get("session_id"),
        "source": provenance.get("source"),
    }
    actor = {key: value for key, value in actor.items() if value is not None}
    return actor or None


def save_graph_mutation(
    path: Path, data: dict[str, Any], *, action: str, target: str | None = None,
    before: dict[str, Any] | None = None, source: str = "cli",
    context: dict[str, Any] | None = None, result: str = "succeeded",
    actor: dict[str, Any] | None = None, reason: str | None = None,
    evidence_refs: list[str] | None = None, decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None, supersedes: list[str] | None = None,
    overrides: list[str] | None = None, operation_id: str | None = None,
    phase: str = "executed",
) -> dict[str, Any]:
    """Save canonical state and append its independently queryable transitions.

    Status-field mutations are promoted into immutable, hash-linked graph child
    records before the canonical document is saved. Finalized nodes receive a
    semantic SHA-256 seal. If journal append fails, the canonical graph is rolled
    back to the exact pre-mutation document. Reads and vector-cache changes do not
    use this API.
    """
    from grapher.integrity import materialize_status_transitions, seal_finalized_nodes
    from grapher.provenance import actor_record, make_history_entry
    from grapher.truth_policy import enforce_new_node_truth_status

    old = before if before is not None else (load_graph(path, normalize=False) if path.is_file() else None)
    config = load_config(path)
    enforce_new_node_truth_status(
        old,
        data,
        enabled=bool(config.get("require_explicit_status", False)),
    )

    operation_id = operation_id or f"operation-{uuid.uuid4().hex}"
    resolved_actor = actor_record(source, actor or _actor_from_context(context))

    # Any explicit finalization performed by a caller is sealed before persistence.
    seal_finalized_nodes(data)
    transition_ids = materialize_status_transitions(
        old,
        data,
        actor=resolved_actor,
        reason=reason,
        operation_id=operation_id,
    )
    # Status transitions may finalize their subject and always finalize themselves.
    seal_finalized_nodes(data)

    enriched_context = dict(context or {})
    if transition_ids:
        enriched_context["status_transition_ids"] = transition_ids

    entry = make_history_entry(
        old, data, action=action, target=target, source=source, result=result,
        before_hash=_stable_hash(old) if old is not None else None,
        after_hash=_stable_hash(data), actor=resolved_actor, reason=reason,
        evidence_refs=evidence_refs, decision_ids=decision_ids,
        requirement_ids=requirement_ids, supersedes=supersedes,
        overrides=overrides, operation_id=operation_id, phase=phase,
        context=enriched_context or None,
    )
    save_graph(path, data)
    try:
        append_history(path, entry)
    except Exception:
        if old is not None:
            save_graph(path, old)
        raise
    return entry


def load_vectors(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_vectors()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("vectors file must be a JSON object")
    data.setdefault("version", 1)
    data.setdefault("vectors", {})
    return data


def save_vectors(path: Path, data: dict[str, Any]) -> None:
    _atomic_write(path, data)


def init_store(
    graph_path: Path,
    *,
    name: str = "knowledge",
    domain: str = "general",
    kinds: list[str] | None = None,
    stages: list[str] | None = None,
    profile: str = "general",
) -> tuple[Path, Path]:
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    if not graph_path.is_file():
        save_graph(
            graph_path,
            empty_graph(
                name=name,
                domain=domain,
                kinds=kinds,
                stages=stages,
                profile=profile,
            ),
        )
        save_config(
            graph_path,
            default_config(profile=profile),
        )
    vpath = vectors_path_for(graph_path)
    if not vpath.is_file():
        save_vectors(vpath, empty_vectors())
    return graph_path, vpath
