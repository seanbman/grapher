from pathlib import Path


def test_install_script_supports_local_checkout_mode():
    script = Path("install.sh").read_text()

    assert 'if [[ "${1:-}" == "--local" ]]' in script
    assert 'pip install --upgrade "$SCRIPT_DIR"' in script
    assert 'Installing Grapher from local checkout:' in script
    assert 'usage: $0 [--local]' in script


def test_local_mode_does_not_require_curl():
    script = Path("install.sh").read_text()

    assert 'if [[ "$LOCAL_INSTALL" -eq 0 ]]; then\n  command -v curl' in script
