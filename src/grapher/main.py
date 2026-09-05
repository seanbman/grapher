"""Top-level CLI dispatcher for transport commands and the existing CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from grapher.format import emit
from grapher.store import resolve_graph_path
from grapher.transport import publish_graph, sync_graph


def _transport_parser(command: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"grapher {command}")
    parser.add_argument("--graph", default=None)
    parser.add_argument("--json", action="store_true")
    if command == "sync":
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--no-vectors", action="store_true")
    return parser


def _run_transport(command: str, argv: list[str]) -> None:
    parser = _transport_parser(command)
    args = parser.parse_args(argv)
    try:
        graph_path = resolve_graph_path(args.graph, create=(command == "sync"))
        if command == "publish":
            result = publish_graph(graph_path)
        else:
            result = sync_graph(
                graph_path,
                force=args.force,
                rebuild_vectors=not args.no_vectors,
            )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    emit(result, as_json=args.json)


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] in {"publish", "sync"}:
        _run_transport(argv[0], argv[1:])
        return

    from grapher.cli import main as legacy_main

    legacy_main()
