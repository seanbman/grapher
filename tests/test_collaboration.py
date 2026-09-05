from pathlib import Path

from grapher import graph as G
from grapher.collaboration import create_arm, create_changeset, reconcile_graph
from grapher.store import init_store, load_graph, save_graph
from grapher.transport import publish_graph


def _base_graph(tmp_path: Path) -> Path:
    path = tmp_path / ".grapher" / "knowledge.json"
    init_store(path)
    graph = load_graph(path)
    G.add_node(graph, type="document", title="Shared", content="base", id="shared")
    save_graph(path, graph)
    publish_graph(path)
    return path


def test_two_agent_arms_merge_independent_work(tmp_path: Path) -> None:
    main = _base_graph(tmp_path)
    arm_a = Path(create_arm(main, actor="agent-a")["graph"])
    arm_b = Path(create_arm(main, actor="agent-b")["graph"])

    graph_a = load_graph(arm_a)
    G.add_node(graph_a, type="document", title="Arm A", content="alpha", id="arm-a")
    save_graph(arm_a, graph_a)
    change_a = create_changeset(arm_a, actor="agent-a")

    graph_b = load_graph(arm_b)
    G.add_node(graph_b, type="document", title="Arm B", content="beta", id="arm-b")
    save_graph(arm_b, graph_b)
    change_b = create_changeset(arm_b, actor="agent-b")

    result = reconcile_graph(main)
    assert result["reconciled"] is True
    merged = load_graph(main)
    assert {"shared", "arm-a", "arm-b"} <= set(merged["nodes"])

    publish_graph(main)
    manifest = (main.parent / "shared" / "manifest.json").read_text(encoding="utf-8")
    assert change_a["changeset_id"] in manifest
    assert change_b["changeset_id"] in manifest


def test_disjoint_fields_on_same_node_merge(tmp_path: Path) -> None:
    main = _base_graph(tmp_path)
    arm_a = Path(create_arm(main, actor="agent-a")["graph"])
    arm_b = Path(create_arm(main, actor="agent-b")["graph"])

    graph_a = load_graph(arm_a)
    graph_a["nodes"]["shared"]["content"] = "updated content"
    graph_a["nodes"]["shared"]["updated_at"] = "2026-09-05T01:00:00Z"
    save_graph(arm_a, graph_a)
    create_changeset(arm_a, actor="agent-a")

    graph_b = load_graph(arm_b)
    graph_b["nodes"]["shared"]["tags"] = ["peer-work"]
    graph_b["nodes"]["shared"]["updated_at"] = "2026-09-05T02:00:00Z"
    save_graph(arm_b, graph_b)
    create_changeset(arm_b, actor="agent-b")

    result = reconcile_graph(main)
    assert result["reconciled"] is True
    node = load_graph(main)["nodes"]["shared"]
    assert node["content"] == "updated content"
    assert node["tags"] == ["peer-work"]
    assert node["updated_at"] == "2026-09-05T02:00:00Z"


def test_same_field_conflict_is_atomic(tmp_path: Path) -> None:
    main = _base_graph(tmp_path)
    arm_a = Path(create_arm(main, actor="agent-a")["graph"])
    arm_b = Path(create_arm(main, actor="agent-b")["graph"])

    graph_a = load_graph(arm_a)
    graph_a["nodes"]["shared"]["content"] = "left"
    save_graph(arm_a, graph_a)
    create_changeset(arm_a, actor="agent-a")

    graph_b = load_graph(arm_b)
    graph_b["nodes"]["shared"]["content"] = "right"
    save_graph(arm_b, graph_b)
    create_changeset(arm_b, actor="agent-b")

    result = reconcile_graph(main)
    assert result["reconciled"] is False
    assert result["conflicts"] == 1
    assert load_graph(main)["nodes"]["shared"]["content"] == "base"
    assert Path(result["conflict_report"]).is_file()
