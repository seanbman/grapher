from pathlib import Path

semantic = Path("tests/test_semantic.py")
text = semantic.read_text(encoding="utf-8")
old = "from grapher.graph import add_node\n"
new = "from grapher.graph import GraphError, add_node\n"
if old not in text:
    raise SystemExit("semantic GraphError import target missing")
semantic.write_text(text.replace(old, new, 1), encoding="utf-8")

modern = Path("tests/test_modernization.py")
text = modern.read_text(encoding="utf-8")
needle = '''    with pytest.raises(GraphError, match="create-only"):
        set_provenance_integrity(graph, "a", "invalidated", reason="later dispute")
'''
replacement = '''    with pytest.raises(GraphError, match="finalized"):
        set_provenance_integrity(graph, "a", "invalidated", reason="later dispute")
'''
if needle not in text:
    raise SystemExit("modernization provenance expectation target missing")
modern.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
