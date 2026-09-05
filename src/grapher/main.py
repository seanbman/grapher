"""Top-level CLI dispatcher for transport and collaboration commands."""

from __future__ import annotations

import argparse
import sys

from grapher.collaboration import create_arm, create_changeset, reconcile_graph
from grapher.format import emit
from grapher.store import resolve_graph_path
from grapher.transport import publish_graph, sync_graph


def _command_parser(command: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"grapher {command}")
    parser.add_argument("--graph", default=None)
    parser.add_argument("--json", action="store_true")
    if command == "sync":
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--no-vectors", action="store_true")
    if command == "arm":
        parser.add_argument("--actor", required=True)
        parser.add_argument("--force", action="store_true")
    if command == "changeset":
        parser.add_argument("--actor", required=True)
    return parser


def _run_command(command: str, argv: list[str]) -> None:
    parser = _command_parser(command)
    args = parser.parse_args(argv)
    try:
        graph_path = resolve_graph_path(
            args.graph,
            create=command in {"sync", "arm", "reconcile"},
        )
        if command == "publish":
            result = publish_graph(graph_path)
        elif command == "sync":
            result = sync_graph(
                graph_path,
                force=args.force,
                rebuild_vectors=not args.no_vectors,
            )
        elif command == "arm":
            result = create_arm(graph_path, actor=args.actor, force=args.force)
        elif command == "changeset":
            result = create_changeset(graph_path, actor=args.actor)
        else:
            result = reconcile_graph(graph_path)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    emit(result, as_json=args.json)


def main() -> None:
    argv = sys.argv[1:]
    commands = {"publish", "sync", "arm", "changeset", "reconcile"}
    if argv and argv[0] in commands:
        _run_command(argv[0], argv[1:])
        return

    from grapher.cli import main as legacy_main

    legacy_main()
