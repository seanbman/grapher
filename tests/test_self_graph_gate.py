from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_self_graph_update.py"
spec = importlib.util.spec_from_file_location("check_self_graph_update", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _write(tmp_path: Path, payload: str) -> Path:
    path = tmp_path / "pass.json"
    path.write_text(payload, encoding="utf-8")
    return path


def test_valid_pass_record_is_accepted(tmp_path: Path):
    path = _write(
        tmp_path,
        '{"id":"p","type":"result","title":"Pass","status":"current",'
        '"content":{"result":"done"},'
        '"provenance":{"actor_id":"agent","source":"test"}}',
    )
    assert module.validate_pass_record(path) == []


def test_pass_record_requires_semantics_and_provenance(tmp_path: Path):
    path = _write(
        tmp_path,
        '{"id":"p","type":"result","title":"Pass","status":"unclassified",'
        '"provenance":{}}',
    )
    errors = module.validate_pass_record(path)
    assert "status must be explicit, not unclassified" in errors
    assert "record must contain non-empty semantic or content payload" in errors
    assert "provenance.actor_id must be non-empty" in errors
    assert "provenance.source must be non-empty" in errors


def test_invalid_json_is_rejected(tmp_path: Path):
    errors = module.validate_pass_record(_write(tmp_path, "not-json"))
    assert errors and errors[0].startswith("invalid JSON:")
