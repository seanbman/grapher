from pathlib import Path


def test_install_script_supports_local_checkout_mode():
    script = Path("install.sh").read_text()

    assert 'if [[ "${1:-}" == "--local" ]]' in script
    assert 'pip install --upgrade "$SCRIPT_DIR[embed]"' in script
    assert 'Installing Grapher from local checkout:' in script
    assert 'usage: $0 [--local]' in script


def test_local_mode_does_not_require_curl():
    script = Path("install.sh").read_text()

    assert 'if [[ "$LOCAL_INSTALL" -eq 0 ]]; then\n  command -v curl' in script


def test_release_install_includes_embed_extra():
    script = Path("install.sh").read_text()

    assert 'grapher[embed] @ git+https://github.com/$REPO.git@$TAG' in script


def test_installer_verifies_embedding_runtime():
    script = Path("install.sh").read_text()

    assert 'import fastembed' in script
    assert 'import numpy' in script
    assert 'Embedding runtime: available' in script
    assert 'Semantic search: enabled' in script
