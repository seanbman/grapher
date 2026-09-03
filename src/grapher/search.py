"""Lexical, semantic, and hybrid search over the knowledge graph."""

from __future__ import annotations

from typing import Any

from pathlib import Path

from grapher.config import load_config
from grapher.embed import EmbedError, Embedder, get_embedder
from grapher.model import embed_text
from grapher.query import (
    apply_truth_ranking,
    matches_filters,
    parse_stage_filter,
    parse_status_filter,
)
from grapher.store import load_vectors, save_vectors, vectors_path_for


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    # vectors are L2-normalized at embed time
    return sum(x * y for x, y in zip(a, b))


def lexical_search(
    graph: dict[str, Any],
    query: str,
    *,
    type: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    verification: str | None = None,
    workflow_state: str | None = None,
    project: str | None = None,
    mission: str | None = None,
    generation: str | None = None,
    actor: str | None = None,
    role: str | None = None,
    as_of: str | None = None,
    exclude_superseded: bool = False,
    current_only: bool = False,
    limit: int = 10,
    truth_rank: bool = True,
    explain_ranking: bool = False,
    graph_path: Path | None = None,
) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    tokens = [t for t in q.split() if t]
    status_set = parse_status_filter(status)
    stage_set = parse_stage_filter(stage)
    config = load_config(graph_path) if graph_path else {}
    hits: list[tuple[float, dict[str, Any]]] = []
    for node in graph["nodes"].values():
        if not matches_filters(
            node,
            type=type,
            tag=tag,
            status=status_set,
            stage=stage_set,
            verification=verification,
            workflow_state=workflow_state,
            project=project, mission=mission, generation=generation,
            actor=actor, role=role, as_of=as_of,
            exclude_superseded=exclude_superseded,
            current_only=current_only,
        ):
            continue
        hay = " ".join(
            [
                str(node.get("title") or ""),
                str(node.get("content") or ""),
                str(node.get("path") or ""),
                " ".join(str(t) for t in (node.get("tags") or [])),
            ]
        ).lower()
        if q in hay:
            score = 1.0
        else:
            matched = sum(1 for t in tokens if t in hay)
            if not matched:
                continue
            score = matched / len(tokens)
        hits.append((score, node))
    hits.sort(key=lambda x: (-x[0], x[1].get("title") or ""))
    results = [
        {"score": round(score, 4), "mode": "lexical", "node": node}
        for score, node in hits[: limit * 3]
    ]
    if truth_rank:
        results = apply_truth_ranking(
            results, config=config, explain=explain_ranking, query=query,
            project=project, mission=mission, generation=generation
        )
    return results[:limit]


def ensure_vectors_meta(
    vectors: dict[str, Any],
    embedder: Embedder,
) -> None:
    vectors["provider"] = embedder.provider
    vectors["model"] = embedder.model
    if embedder.dims is not None:
        vectors["dims"] = embedder.dims


def upsert_node_vector(
    graph_path: Path,
    node: dict[str, Any],
    *,
    embedder: Embedder | None = None,
) -> None:
    text = embed_text(node)
    if not text.strip():
        return
    try:
        emb = embedder or get_embedder()
    except EmbedError:
        return
    vec = emb.embed([text])[0]
    vpath = vectors_path_for(graph_path)
    vectors = load_vectors(vpath)
    # model change → wipe
    if vectors.get("model") and vectors["model"] != emb.model:
        vectors["vectors"] = {}
    ensure_vectors_meta(vectors, emb)
    vectors["vectors"][node["id"]] = vec
    save_vectors(vpath, vectors)


def remove_node_vector(graph_path: Path, node_id: str) -> None:
    vpath = vectors_path_for(graph_path)
    if not vpath.is_file():
        return
    vectors = load_vectors(vpath)
    if node_id in vectors.get("vectors", {}):
        del vectors["vectors"][node_id]
        save_vectors(vpath, vectors)


def reindex(
    graph: dict[str, Any],
    graph_path: Path,
    *,
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    emb = embedder or get_embedder()
    nodes = list(graph["nodes"].values())
    texts = [embed_text(n) for n in nodes]
    # skip empty texts but keep alignment via indices
    indices = [i for i, t in enumerate(texts) if t.strip()]
    batch = [texts[i] for i in indices]
    vectors = {
        "version": 1,
        "model": emb.model,
        "provider": emb.provider,
        "dims": emb.dims,
        "vectors": {},
    }
    if batch:
        vecs = emb.embed(batch)
        ensure_vectors_meta(vectors, emb)
        for i, vec in zip(indices, vecs):
            vectors["vectors"][nodes[i]["id"]] = vec
    vpath = vectors_path_for(graph_path)
    save_vectors(vpath, vectors)
    return {
        "indexed": len(vectors["vectors"]),
        "skipped_empty": len(nodes) - len(indices),
        "model": vectors["model"],
        "provider": vectors["provider"],
        "dims": vectors.get("dims"),
        "path": str(vpath),
    }


def semantic_search(
    graph: dict[str, Any],
    graph_path: Path,
    query: str,
    *,
    type: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    verification: str | None = None,
    workflow_state: str | None = None,
    project: str | None = None,
    mission: str | None = None,
    generation: str | None = None,
    actor: str | None = None,
    role: str | None = None,
    as_of: str | None = None,
    exclude_superseded: bool = False,
    current_only: bool = False,
    limit: int = 10,
    truth_rank: bool = True,
    explain_ranking: bool = False,
    embedder: Embedder | None = None,
) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []
    emb = embedder or get_embedder()
    vpath = vectors_path_for(graph_path)
    vectors = load_vectors(vpath)
    store = vectors.get("vectors") or {}

    # auto-reindex if empty or model mismatch / incomplete coverage
    need_reindex = False
    if not store:
        need_reindex = True
    elif vectors.get("model") != emb.model:
        need_reindex = True
    elif any(nid not in store for nid in graph["nodes"]):
        # partial: embed missing only
        missing = [
            n
            for nid, n in graph["nodes"].items()
            if nid not in store and embed_text(n).strip()
        ]
        if missing:
            texts = [embed_text(n) for n in missing]
            vecs = emb.embed(texts)
            ensure_vectors_meta(vectors, emb)
            for n, vec in zip(missing, vecs):
                store[n["id"]] = vec
            vectors["vectors"] = store
            save_vectors(vpath, vectors)

    if need_reindex:
        reindex(graph, graph_path, embedder=emb)
        vectors = load_vectors(vpath)
        store = vectors.get("vectors") or {}

    qvec = emb.embed([q])[0]
    status_set = parse_status_filter(status)
    stage_set = parse_stage_filter(stage)
    config = load_config(graph_path)
    hits: list[tuple[float, dict[str, Any]]] = []
    for nid, vec in store.items():
        node = graph["nodes"].get(nid)
        if not node:
            continue
        if not matches_filters(
            node,
            type=type,
            tag=tag,
            status=status_set,
            stage=stage_set,
            verification=verification,
            workflow_state=workflow_state,
            project=project, mission=mission, generation=generation,
            actor=actor, role=role, as_of=as_of,
            exclude_superseded=exclude_superseded,
            current_only=current_only,
        ):
            continue
        score = cosine(qvec, vec)
        hits.append((score, node))
    hits.sort(key=lambda x: (-x[0], x[1].get("title") or ""))
    results = [
        {"score": round(score, 4), "mode": "semantic", "node": node}
        for score, node in hits[: limit * 3]
    ]
    if truth_rank:
        results = apply_truth_ranking(
            results, config=config, explain=explain_ranking, query=query,
            project=project, mission=mission, generation=generation
        )
    return results[:limit]


def hybrid_search(
    graph: dict[str, Any],
    graph_path: Path,
    query: str,
    *,
    type: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    verification: str | None = None,
    workflow_state: str | None = None,
    project: str | None = None,
    mission: str | None = None,
    generation: str | None = None,
    actor: str | None = None,
    role: str | None = None,
    as_of: str | None = None,
    exclude_superseded: bool = False,
    current_only: bool = False,
    limit: int = 10,
    truth_rank: bool = True,
    explain_ranking: bool = False,
    embedder: Embedder | None = None,
) -> list[dict[str, Any]]:
    common = dict(
        type=type,
        tag=tag,
        status=status,
        stage=stage,
        verification=verification,
        workflow_state=workflow_state,
        project=project, mission=mission, generation=generation,
        actor=actor, role=role, as_of=as_of,
        exclude_superseded=exclude_superseded,
        current_only=current_only,
        truth_rank=False,
    )
    try:
        sem = semantic_search(
            graph,
            graph_path,
            query,
            limit=limit * 2,
            embedder=embedder,
            **common,
        )
    except EmbedError:
        return lexical_search(
            graph,
            query,
            limit=limit,
            truth_rank=truth_rank,
            explain_ranking=explain_ranking,
            graph_path=graph_path,
            **common,
        )
    lex = lexical_search(
        graph,
        query,
        limit=limit * 2,
        graph_path=graph_path,
        **common,
    )
    by_id: dict[str, dict[str, Any]] = {}
    for hit in sem:
        nid = hit["node"]["id"]
        by_id[nid] = {
            "score": hit["score"],
            "mode": "hybrid",
            "semantic_score": hit["score"],
            "lexical_score": 0.0,
            "node": hit["node"],
        }
    for hit in lex:
        nid = hit["node"]["id"]
        if nid in by_id:
            by_id[nid]["lexical_score"] = hit["score"]
            by_id[nid]["score"] = round(
                by_id[nid]["semantic_score"] + 0.15 * hit["score"], 4
            )
        else:
            by_id[nid] = {
                "score": round(0.5 * hit["score"], 4),
                "mode": "hybrid",
                "semantic_score": 0.0,
                "lexical_score": hit["score"],
                "node": hit["node"],
            }
    ranked = sorted(
        by_id.values(),
        key=lambda h: (-h["score"], h["node"].get("title") or ""),
    )
    results = ranked[: limit * 3]
    if truth_rank:
        config = load_config(graph_path)
        results = apply_truth_ranking(
            results, config=config, explain=explain_ranking, query=query,
            project=project, mission=mission, generation=generation
        )
    return results[:limit]


def search(
    graph: dict[str, Any],
    graph_path: Path,
    query: str,
    *,
    mode: str = "semantic",
    type: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    verification: str | None = None,
    workflow_state: str | None = None,
    project: str | None = None,
    mission: str | None = None,
    generation: str | None = None,
    actor: str | None = None,
    role: str | None = None,
    as_of: str | None = None,
    exclude_superseded: bool = False,
    current_only: bool = False,
    limit: int = 10,
    truth_rank: bool = True,
    explain_ranking: bool = False,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    if mission and not generation and any(x in query.lower() for x in ("current", "now", "complete", "accepted", "state")):
        candidates = [n for n in graph.get("nodes", {}).values()
                      if (n.get("scope") or {}).get("mission_id") == mission
                      and (n.get("scope") or {}).get("generation_id")
                      and n.get("status") in ("current", "canonical_spec")]
        active = [n for n in candidates if n.get("workflow_state") == "active"]
        winner = (active or candidates)
        if winner:
            generation = sorted(winner, key=lambda n: n.get("updated_at", ""), reverse=True)[0]["scope"]["generation_id"]
    if kind:
        requested = {x.strip() for x in kind.split(",") if x.strip()}
        if not requested.intersection((graph.get("graph") or {}).get("kinds") or []):
            return []
    common = dict(
        type=type,
        tag=tag,
        status=status,
        stage=stage,
        verification=verification,
        workflow_state=workflow_state,
        project=project, mission=mission, generation=generation,
        actor=actor, role=role, as_of=as_of,
        exclude_superseded=exclude_superseded,
        current_only=current_only,
        limit=limit,
        truth_rank=truth_rank,
        explain_ranking=explain_ranking,
    )
    mode = mode.lower()
    if mode == "lexical":
        return lexical_search(graph, query, graph_path=graph_path, **common)
    if mode == "hybrid":
        return hybrid_search(graph, graph_path, query, **common)
    if mode == "semantic":
        try:
            return semantic_search(graph, graph_path, query, **common)
        except EmbedError:
            return lexical_search(graph, query, graph_path=graph_path, **common)
    raise ValueError(f"unknown search mode: {mode}")
