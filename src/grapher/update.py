from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

RELEASES_URL = "https://api.github.com/repos/seanbman/grapher/releases?per_page=20"
DISABLE_ENV = "GRAPHER_NO_UPDATE_CHECK"

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$")
_STAGE_RANK = {"a": 0, "b": 1, "rc": 2, None: 3}


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    version: str
    html_url: str
    prerelease: bool


def _key(version: str) -> tuple[int, int, int, int, int]:
    match = _VERSION_RE.match(version.strip())
    if not match:
        raise ValueError(f"unsupported version: {version}")
    major, minor, patch = map(int, match.group(1, 2, 3))
    stage = match.group(4)
    serial = int(match.group(5) or 0)
    return major, minor, patch, _STAGE_RANK[stage], serial


def latest_release(*, timeout: float = 2.0) -> ReleaseInfo | None:
    request = urllib.request.Request(
        RELEASES_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "grapher-update-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            releases = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    candidates: list[ReleaseInfo] = []
    for release in releases:
        if release.get("draft"):
            continue
        tag = str(release.get("tag_name") or "")
        try:
            _key(tag)
        except ValueError:
            continue
        candidates.append(
            ReleaseInfo(
                tag=tag,
                version=tag.removeprefix("v"),
                html_url=str(release.get("html_url") or ""),
                prerelease=bool(release.get("prerelease")),
            )
        )
    return max(candidates, key=lambda item: _key(item.version), default=None)


def update_available(current_version: str, release: ReleaseInfo | None) -> bool:
    if release is None:
        return False
    try:
        return _key(release.version) > _key(current_version)
    except ValueError:
        return False


def maybe_notify(current_version: str) -> None:
    """Check GitHub on human TTY launches and print a non-fatal update notice."""
    if os.environ.get(DISABLE_ENV) or not sys.stderr.isatty():
        return
    release = latest_release()
    if update_available(current_version, release):
        assert release is not None
        print(
            f"Grapher {release.tag} is available (installed {current_version}). "
            "Run the repository install.sh again to update.",
            file=sys.stderr,
        )
