from pathlib import Path


def test_dash_type_filter_defaults_to_all_node_types():
    source = Path("src/grapher/viz/app.py").read_text()
    dropdown = source.split('id="filter-types",', 1)[1].split('multi=True,', 1)[0]
    assert "value=[]" in dropdown
    assert "value=sorted(NODE_TYPES)" not in dropdown
