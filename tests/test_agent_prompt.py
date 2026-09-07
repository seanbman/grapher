from grapher.agent_prompt import OPERATING_SEQUENCE, render_agent_context
from grapher.codex_ctx import render_context_markdown
from grapher.model import empty_graph
from grapher.graph import add_node, link


def test_generalized_agent_prompt_is_deterministic_and_truth_aware():
    graph = empty_graph()
    add_node(
        graph,
        id="b",
        type="finding",
        title="Second",
        content="later",
        status="historical",
        verification="verified",
        scope={"project_id": "grapher", "generation_id": "g1"},
    )
    add_node(
        graph,
        id="a",
        type="requirement",
        title="First",
        content="required",
        status="canonical_spec",
        verification="verified",
        scope={"project_id": "grapher", "generation_id": "g1"},
    )
    link(graph, from_id="a", to_id="b", rel="references")

    first = render_agent_context(graph, name="x", consumer="agent")
    second = render_agent_context(graph, name="x", consumer="agent")

    assert first == second
    assert OPERATING_SEQUENCE == ("READ", "SEARCH", "ACT", "RECORD", "VALIDATE", "PUBLISH")
    assert "canonical_spec" in first
    assert "historical" in first
    assert "generation_id=g1" in first
    assert first.index("### First") < first.index("### Second")
    assert "Do not infer truth status from recency alone" in first


def test_codex_renderer_reuses_generalized_contract():
    graph = empty_graph()
    add_node(graph, id="n", type="finding", title="Known", content="state", status="current")
    rendered = render_context_markdown(graph, name="project")

    assert "Consumer: `codex`" in rendered
    assert "**READ**" in rendered
    assert "**SEARCH**" in rendered
    assert "**PUBLISH**" in rendered
    assert "Known (`n`)" in rendered
