"""Top-level CLI dispatcher for transport, interactive UI, and long-form CLI."""

from __future__ import annotations

import argparse
import sys

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


def _run_legacy(argv: list[str]) -> None:
    from grapher.cli import main as legacy_main

    previous = sys.argv
    try:
        sys.argv = ["grapher", *argv]
        legacy_main()
    finally:
        sys.argv = previous


def _dispatch(argv: list[str]) -> None:
    if argv and argv[0] in {"publish", "sync"}:
        _run_transport(argv[0], argv[1:])
    else:
        _run_legacy(argv)


def _interactive_loop() -> None:
    from grapher.interactive import menu

    while True:
        argv = menu()
        if argv is None:
            return
        if not argv:
            continue
        _dispatch(argv)


def main() -> None:
    argv = sys.argv[1:]
    interactive_terminal = sys.stdin.isatty() and sys.stdout.isatty()

    if not argv and interactive_terminal:
        _interactive_loop()
        return

    if argv == ["init"] and interactive_terminal:
        from grapher.interactive import guided_init_args

        guided = guided_init_args()
        if guided is None:
            return
        _dispatch(guided)
        return

    _dispatch(argv)
