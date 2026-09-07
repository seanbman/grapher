from __future__ import annotations

from grapher import interactive


def test_guided_init_translates_answers_to_existing_cli(monkeypatch):
    answers = iter(["demo", "custom-domain", "knowledge,decision"])
    monkeypatch.setattr(interactive, "ask", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(interactive, "choose", lambda *args, **kwargs: "software")
    monkeypatch.setattr(interactive, "confirm", lambda *args, **kwargs: True)

    argv = interactive.guided_init_args()

    assert argv == [
        "init",
        "--name",
        "demo",
        "--profile",
        "software",
        "--domain",
        "custom-domain",
        "--kind",
        "knowledge,decision",
        "--all-stages",
    ]


def test_menu_exit_returns_none(monkeypatch):
    monkeypatch.setattr(interactive, "choose", lambda *args, **kwargs: "exit")
    assert interactive.menu() is None
