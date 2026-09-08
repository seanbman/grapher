# Grapher installation and updates

## Index

- [Supported beta](#supported-beta)
- [Linux installation](#linux-installation)
- [What the installer does](#what-the-installer-does)
- [Verify installation](#verify-installation)
- [Updating](#updating)
- [Update checks](#update-checks)
- [Development installation](#development-installation)
- [Troubleshooting](#troubleshooting)
- [Appendix — Process flow](#appendix--process-flow)

This guide is the canonical human-facing installation and update reference for Grapher.

## Supported beta

The current public beta line is **v0.7.0b1**. GitHub Releases are the distribution/version authority for normal installations; `main` is development state and is not treated as an installed release.

## Linux installation

Requirements: Linux and Python 3.10+. Normal release installation also requires network access. The one-line bootstrap uses `curl`.

```bash
curl -fsSL https://raw.githubusercontent.com/seanbman/grapher/main/install.sh | bash
```

From an existing repository checkout, install the latest published release with:

```bash
bash install.sh
```

To install the code in the **current checkout** instead of a published release, use:

```bash
bash install.sh --local
```

`--local` is intended for development/main-branch testing and does not resolve a GitHub release. The installer does not require `sudo`.

## What the installer does

The installer creates an isolated Python environment under `~/.local/share/grapher/venv` and exposes the executable through `~/.local/bin/grapher`.

In normal mode it resolves and installs a published Grapher GitHub release. In `--local` mode it installs the repository checkout containing `install.sh`.

If `~/.local/bin` is not already on `PATH`, add it in your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

This installation is intentionally separate from system Python packages.

## Verify installation

```bash
grapher --version
grapher --help
command -v grapher
```

For a local checkout install, `command -v grapher` should normally resolve to `~/.local/bin/grapher` unless another earlier PATH entry shadows it.

For a new project, continue with the repository README and `grapher init`.

## Updating

For published releases, re-run the same installer. It resolves the published release line and replaces the isolated installed environment without requiring a system-wide Python mutation.

```bash
curl -fsSL https://raw.githubusercontent.com/seanbman/grapher/main/install.sh | bash
```

For current checkout/main-branch testing:

```bash
git pull
./install.sh --local
```

## Update checks

Interactive Grapher launches query published GitHub releases and compare the installed semantic version with available releases, including prereleases while on the beta line. A newer release produces a non-blocking notice. Network failure, GitHub unavailability, or offline use does not prevent Grapher from starting.

Non-interactive/automation execution stays quiet. To explicitly suppress checks in an interactive environment:

```bash
GRAPHER_NO_UPDATE_CHECK=1 grapher
```

Update discovery never mutates a project graph and never installs an update automatically.

## Development installation

Contributors who intentionally want editable source behavior can use a repository-local virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[embed,dash]"
```

Or use the managed user installation path against the current checkout:

```bash
./install.sh --local
```

## Troubleshooting

If `grapher` is not found after installation, verify `~/.local/bin` is on `PATH`.

If a local install appears to run an older Grapher, inspect command resolution:

```bash
which -a grapher
command -v grapher
```

The intended managed launcher is `~/.local/bin/grapher`. An earlier PATH entry can shadow it. Also confirm that `./install.sh --local` printed `Installing Grapher from local checkout:` rather than a release tag.

If Python is too old, install Python 3.10+ using the Linux distribution's package mechanism and rerun the installer. For update-check network failures, no repair is required: the check is intentionally best-effort and Grapher continues offline.

## Appendix — Process flow

```mermaid
flowchart LR
    R["Published GitHub release\ncode: .github/workflows/publish-beta.yml\ninception: 13a1f2c\ncurrent: main"] --> I["Release install\ncode: install.sh\ninception: 13a1f2c\ncurrent: fix/local-installer"]
    L["Local source checkout\ncode: install.sh --local\ninception: 619b329\ncurrent: fix/local-installer"] --> I2["Local checkout install\ncode: install.sh\ninception: 619b329\ncurrent: fix/local-installer"]
    I --> V["Isolated user environment\ncode: ~/.local/share/grapher/venv\ninception: 13a1f2c\ncurrent: main"]
    I2 --> V
    V --> C["Interactive launch\ncode: src/grapher/main.py\ninception: 13a1f2c\ncurrent: main"]
    C --> U["Non-blocking release check\ncode: src/grapher/update.py\ninception: 13a1f2c\ncurrent: main"]
```

Release anchor: `13a1f2ca016ef50c7f2fdc71a9ef9bfd437cc498` (v0.7.0b1).