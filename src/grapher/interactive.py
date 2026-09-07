from __future__ import annotations

import json
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

from grapher.config import load_config, save_config
from grapher.store import resolve_graph_path


def _prompt(text: str, default: str = "", option_count: int | None = None) -> str | None:
    bindings = KeyBindings()
    state = {"index": 0}

    def _set_choice(event, delta: int) -> None:
        if not option_count:
            return
        state["index"] = (state["index"] + delta) % option_count
        value = str(state["index"] + 1)
        event.current_buffer.text = value
        event.current_buffer.cursor_position = len(value)

    @bindings.add("up")
    def _up(event) -> None:
        _set_choice(event, -1)

    @bindings.add("down")
    def _down(event) -> None:
        _set_choice(event, 1)

    @bindings.add("escape")
    @bindings.add("c-c")
    def _cancel(event) -> None:
        event.app.exit(exception=KeyboardInterrupt())

    session = PromptSession(key_bindings=bindings)
    try:
        return session.prompt(text, default=default)
    except (EOFError, KeyboardInterrupt):
        return None


def choose(title: str, text: str, values: list[tuple[str, str]]) -> str | None:
    if not values:
        return None
    print(f"\n{title}\n{text}")
    for index, (_, label) in enumerate(values, start=1):
        print(f"  {index}. {label}")
    print("  q. Back / Exit")
    while True:
        answer = _prompt(f"Select [1-{len(values)}, q]: ", option_count=len(values))
        if answer is None:
            return None
        normalized = answer.strip().lower()
        if normalized in {"q", "quit", "exit", "back"}:
            return None
        if normalized.isdigit():
            index = int(normalized) - 1
            if 0 <= index < len(values):
                return values[index][0]
        print("Invalid selection. Use a number, ↑/↓ then Enter, or q to exit.")


def ask(title: str, text: str, default: str = "") -> str | None:
    print(f"\n{title}")
    suffix = f" [{default}]" if default else ""
    answer = _prompt(f"{text}{suffix}: ")
    if answer is None:
        return None
    return answer if answer else default


def confirm(title: str, text: str) -> bool | None:
    print(f"\n{title}")
    while True:
        answer = _prompt(f"{text} [y/n, q]: ")
        if answer is None:
            return None
        normalized = answer.strip().lower()
        if normalized in {"q", "quit", "exit", "back"}:
            return None
        if normalized in {"y", "yes"}:
            return True
        if normalized in {"n", "no"}:
            return False
        print("Please enter y, n, or q.")


def show(title: str, text: str) -> None:
    print(f"\n{title}\n{text}")


def guided_init_args() -> list[str] | None:
    name = ask("Grapher setup", "Graph/project name", Path.cwd().name)
    if name is None:
        return None
    profile = choose(
        "Grapher setup",
        "Profile",
        [
            ("general", "General"),
            ("software", "Software"),
            ("product", "Product"),
            ("research", "Research"),
            ("campaign", "Campaign"),
            ("operations", "Operations"),
        ],
    )
    if profile is None:
        return None
    domain = ask("Grapher setup", "Domain (blank = profile default)", "")
    if domain is None:
        return None
    kinds = ask("Grapher setup", "Kinds, comma separated (blank = profile defaults)", "")
    if kinds is None:
        return None
    all_stages = confirm("Grapher setup", "Enable all lifecycle stages?")
    if all_stages is None:
        return None
    argv = ["init", "--name", name, "--profile", profile]
    if domain:
        argv += ["--domain", domain]
    if kinds:
        argv += ["--kind", kinds]
    if all_stages:
        argv.append("--all-stages")
    return argv


def edit_config() -> None:
    try:
        graph_path = resolve_graph_path()
    except FileNotFoundError as exc:
        show("Grapher configuration", str(exc))
        return
    config = load_config(graph_path)
    domain = ask("Grapher configuration", "Domain", str(config.get("domain") or ""))
    if domain is None:
        return
    require_status = confirm(
        "Grapher configuration",
        "Require explicit truth status for new authored records?",
    )
    if require_status is None:
        return
    config["domain"] = domain
    config["require_explicit_status"] = require_status
    save_config(graph_path, config)
    show("Grapher configuration", json.dumps(config, indent=2)[:12000])


def menu() -> list[str] | None:
    action = choose(
        "Grapher",
        f"Workspace: {Path.cwd()}",
        [
            ("init", "Initialize Grapher"),
            ("search", "Search graph"),
            ("add", "Add a record"),
            ("audit", "Audit graph"),
            ("publish", "Publish shared state"),
            ("sync", "Sync shared state"),
            ("config", "Edit configuration"),
            ("exit", "Exit"),
        ],
    )
    if action in {None, "exit"}:
        return None
    if action == "init":
        return guided_init_args()
    if action == "config":
        edit_config()
        return []
    if action == "search":
        query = ask("Grapher search", "Query", "")
        return ["search", query] if query else []
    if action == "add":
        node_type = ask("Add record", "Type", "note")
        if node_type is None:
            return []
        title = ask("Add record", "Title", "")
        if not title:
            return []
        content = ask("Add record", "Content", "")
        if content is None:
            return []
        status = ask("Add record", "Truth status", "current")
        if status is None:
            return []
        return ["add", "--type", node_type or "note", "--title", title, "--content", content, "--status", status or "current"]
    return [action]
