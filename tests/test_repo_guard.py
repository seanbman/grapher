from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from grapher.repo_guard import (
    assert_repository_safe,
    ensure_repository_guard,
    repository_guard_status,
)
from grapher.store import init_store
from grapher.transport import publish_graph


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    assert _git(root, "init").returncode == 0
    graph = root / ".grapher" / "knowledge.json"
    init_store(graph, name="guard-test")
    return root, graph


def test_init_installs_selective_ignore_and_pre_commit_guard(tmp_path: Path):
    root, graph = _repo(tmp_path)

    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert ".grapher/knowledge.json" in ignore
    assert ".grapher/history.jsonl" in ignore
    assert ".grapher/shared/" not in ignore
    assert ".grapher/config.json" not in ignore

    status = repository_guard_status(graph)
    assert status["clean"] is True
    assert status["pre_commit_guard"]["installed"] is True

    assert _git(root, "check-ignore", ".grapher/knowledge.json").returncode == 0
    assert _git(root, "check-ignore", ".grapher/shared/knowledge.json").returncode != 0


def test_broad_grapher_ignore_is_replaced_not_preserved(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    assert _git(root, "init").returncode == 0
    (root / ".gitignore").write_text(".grapher/\n.keep-me\n", encoding="utf-8")
    graph = root / ".grapher" / "knowledge.json"

    init_store(graph, name="guard-test")

    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "\n.grapher/\n" not in f"\n{ignore}\n"
    assert ".keep-me" in ignore
    assert ".grapher/knowledge.json" in ignore


def test_repo_guard_rejects_force_added_runtime_state(tmp_path: Path):
    root, graph = _repo(tmp_path)
    assert _git(root, "add", "-f", ".grapher/knowledge.json").returncode == 0

    status = repository_guard_status(graph)
    assert status["clean"] is False
    assert ".grapher/knowledge.json" in status["forbidden_tracked"]

    with pytest.raises(ValueError, match="local runtime state is tracked"):
        assert_repository_safe(graph)
    with pytest.raises(ValueError, match="local runtime state is tracked"):
        publish_graph(graph)


def test_repo_guard_allows_config_and_shared_publication(tmp_path: Path):
    root, graph = _repo(tmp_path)
    publish_graph(graph)
    assert _git(root, "add", ".grapher/config.json", ".grapher/shared").returncode == 0

    status = repository_guard_status(graph)
    assert status["clean"] is True
    assert ".grapher/config.json" in status["safe_tracked"]
    assert any(path.startswith(".grapher/shared/") for path in status["safe_tracked"])


def test_pre_commit_hook_blocks_staged_runtime_state(tmp_path: Path):
    root, graph = _repo(tmp_path)
    assert _git(root, "add", "-f", ".grapher/knowledge.json").returncode == 0
    hook = Path(repository_guard_status(graph)["pre_commit_guard"]["path"])

    result = subprocess.run([str(hook)], cwd=root, text=True, capture_output=True)

    assert result.returncode == 1
    assert "local runtime state is staged" in result.stderr


def test_existing_pre_commit_hook_is_preserved(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    assert _git(root, "init").returncode == 0
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")
    graph = root / ".grapher" / "knowledge.json"

    init_store(graph, name="guard-test")
    setup = ensure_repository_guard(graph)

    assert hook.read_text(encoding="utf-8") == "#!/bin/sh\necho custom\n"
    assert setup["pre_commit_setup"]["reason"] == "existing pre-commit hook preserved"
