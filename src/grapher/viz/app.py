"""Dash app for interactive 3D knowledge graph exploration."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from grapher.model import BUILTIN_NODE_TYPES, NODE_TYPES
from grapher.store import load_graph
from grapher.viz.adapter import TYPE_COLORS, export_view, filter_edges, filter_nodes, graph_summary
from grapher.registry import VIEW_MODE_LABELS, TRUTH_STATUSES, LIFECYCLE_STAGES, VERIFICATION_STATES
from grapher.viz.figure import build_figure, node_detail_markdown
from grapher.viz.layout3d import compute_layout


def _require_dash():
    try:
        import dash
        from dash import Dash, Input, Output, State, dcc, html, no_update
    except ImportError as e:
        raise ImportError(
            "dashboard requires the dash extra.\n"
            "  uv tool install -e \"/path/to/grapher[embed,dash]\" --force\n"
            "  # or: pip install 'grapher[dash]'"
        ) from e
    return dash, Dash, Input, Output, State, dcc, html, no_update


def create_app(graph_path: Path, *, view_mode: str = "knowledge") -> Any:
    dash, Dash, Input, Output, State, dcc, html, no_update = _require_dash()

    app = Dash(__name__, title="grapher")
    app.config.suppress_callback_exceptions = True

    # Shared mutable cache so reload refreshes from disk
    cache: dict[str, Any] = {
        "graph": load_graph(graph_path),
        "positions": {},
        "path": graph_path,
        "view_mode": view_mode,
    }
    cache["positions"][view_mode] = compute_layout(cache["graph"], view_mode=view_mode)

    type_options = [
        {"label": t, "value": t}
        for t in sorted(BUILTIN_NODE_TYPES | {n.get("type", "other") for n in cache["graph"]["nodes"].values()})
    ]

    legend_items = []
    for t in sorted(TYPE_COLORS):
        legend_items.append(
            html.Span(
                [
                    html.Span(
                        style={
                            "display": "inline-block",
                            "width": "10px",
                            "height": "10px",
                            "borderRadius": "50%",
                            "background": TYPE_COLORS[t],
                            "marginRight": "6px",
                        }
                    ),
                    t,
                ],
                style={"marginRight": "14px", "fontSize": "12px", "color": "#b8bcc4"},
            )
        )

    app.layout = html.Div(
        [
            dcc.Store(id="selected-node"),
            dcc.Store(id="reload-token", data=0),
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("grapher", style={"margin": "0", "fontSize": "22px"}),
                            html.Div(
                                ("v1 compatibility view — migrate for lifecycle and provenance features" if cache["graph"].get("version", 1) == 1 else "v2 canonical work graph"),
                                style={"fontSize": "12px", "color": "#F58518", "marginTop": "4px"},
                            ),
                            html.Div(
                                str(graph_path),
                                style={
                                    "fontSize": "12px",
                                    "color": "#8b909a",
                                    "marginTop": "4px",
                                    "wordBreak": "break-all",
                                },
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                    html.Button(
                        "Reload",
                        id="btn-reload",
                        n_clicks=0,
                        style=_btn_style(),
                    ),
                ],
                style=_header_style(),
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("View", style=_label_style()),
                            dcc.Dropdown(id="filter-view", options=[{"label": label, "value": key} for key, label in VIEW_MODE_LABELS.items()], value=view_mode, clearable=False),
                            html.Label("Types", style={**_label_style(), "marginTop": "12px"}),
                            dcc.Dropdown(
                                id="filter-types",
                                options=type_options,
                                value=sorted(NODE_TYPES),
                                multi=True,
                                placeholder="All types",
                                style={"background": "#1a1d24"},
                            ),
                            html.Label("Truth status", style={**_label_style(), "marginTop": "12px"}),
                            dcc.Dropdown(id="filter-status", options=[{"label": x, "value": x} for x in sorted(TRUTH_STATUSES)], multi=True),
                            html.Label("Lifecycle stage", style={**_label_style(), "marginTop": "12px"}),
                            dcc.Dropdown(id="filter-stage", options=[{"label": x, "value": x} for x in sorted(LIFECYCLE_STAGES)], multi=True),
                            html.Label("Verification", style={**_label_style(), "marginTop": "12px"}),
                            dcc.Dropdown(id="filter-verification", options=[{"label": x, "value": x} for x in sorted(VERIFICATION_STATES)], clearable=True),
                            html.Label("Mission generation", style={**_label_style(), "marginTop": "12px"}),
                            dcc.Input(id="filter-generation", type="text", debounce=True, style=_input_style()),
                            html.Label("Search", style={**_label_style(), "marginTop": "12px"}),
                            dcc.Input(
                                id="filter-search",
                                type="text",
                                placeholder="title, content, tags, path…",
                                debounce=True,
                                style=_input_style(),
                            ),
                            dcc.Checklist(
                                id="filter-pending",
                                options=[{"label": " Pending only", "value": "pending"}],
                                value=[],
                                style={"marginTop": "12px", "color": "#c5c9d1"},
                            ),
                            html.Label("Export filtered view", style={**_label_style(), "marginTop": "12px"}),
                            dcc.Dropdown(id="export-format", options=[{"label": "Interactive HTML", "value": "html"}, {"label": "Filtered JSON", "value": "json"}, {"label": "Node CSV", "value": "nodes-csv"}, {"label": "Edge CSV", "value": "edges-csv"}], value="json", clearable=False),
                            html.Button("Download", id="btn-export", n_clicks=0, style={**_btn_style(), "marginTop": "8px"}),
                            dcc.Download(id="download-export"),
                            html.Div(legend_items, style={"marginTop": "16px", "lineHeight": "1.8"}),
                            html.Hr(style={"borderColor": "#2a2e38", "margin": "16px 0"}),
                            html.Div([html.H3("Graph health"), html.Pre(str(graph_summary(cache["graph"])), style={"whiteSpace": "pre-wrap"})], style=_detail_style()),
                            html.Hr(style={"borderColor": "#2a2e38", "margin": "16px 0"}),
                            html.Div(id="detail-panel", style=_detail_style()),
                        ],
                        style=_sidebar_style(),
                    ),
                    html.Div(
                        [
                            dcc.Graph(
                                id="graph-3d",
                                style={"height": "calc(100vh - 72px)"},
                                config={
                                    "displaylogo": False,
                                    "toImageButtonOptions": {"format": "png", "filename": "grapher-view"},
                                },
                            )
                        ],
                        style={"flex": "1", "minWidth": "0"},
                    ),
                ],
                style={"display": "flex", "height": "calc(100vh - 64px)"},
            ),
        ],
        style=_page_style(),
    )

    @app.callback(
        Output("reload-token", "data"),
        Input("btn-reload", "n_clicks"),
        State("reload-token", "data"),
        prevent_initial_call=True,
    )
    def _reload(n_clicks, token):
        cache["graph"] = load_graph(cache["path"])
        cache["positions"] = {}
        return (token or 0) + 1

    @app.callback(
        Output("graph-3d", "figure"),
        Input("filter-view", "value"),
        Input("filter-types", "value"),
        Input("filter-status", "value"),
        Input("filter-stage", "value"),
        Input("filter-verification", "value"),
        Input("filter-generation", "value"),
        Input("filter-search", "value"),
        Input("filter-pending", "value"),
        Input("selected-node", "data"),
        Input("reload-token", "data"),
    )
    def _update_figure(view, types, statuses, stages, verification, generation, search, pending_vals, selected, _token):
        pending_only = bool(pending_vals and "pending" in pending_vals)
        active_view = view or cache.get("view_mode", "knowledge")
        if active_view not in cache["positions"]:
            cache["positions"][active_view] = compute_layout(cache["graph"], view_mode=active_view)
        return build_figure(
            cache["graph"],
            positions=cache["positions"][active_view],
            types=types or [],
            search=search or "",
            pending_only=pending_only,
            status=",".join(statuses or []), stage=",".join(stages or []),
            verification=verification, generation=generation or None,
            selected_id=selected,
            view_mode=view or cache.get("view_mode", "knowledge"),
        )

    @app.callback(
        Output("download-export", "data"),
        Input("btn-export", "n_clicks"),
        State("export-format", "value"), State("filter-view", "value"),
        State("filter-types", "value"), State("filter-search", "value"),
        State("filter-status", "value"), State("filter-stage", "value"),
        State("filter-verification", "value"), State("filter-generation", "value"),
        prevent_initial_call=True,
    )
    def _export(_clicks, fmt, view, types, search, statuses, stages, verification, generation):
        if fmt == "html":
            figure = build_figure(cache["graph"], types=types, search=search or "",
                                  status=",".join(statuses or []), stage=",".join(stages or []),
                                  verification=verification, generation=generation or None, view_mode=view)
            return dcc.send_string(figure.to_html(include_plotlyjs=True, full_html=True), "grapher-view.html")
        content, filename = export_view(
            cache["graph"], format=fmt, view_mode=view, types=types, search=search or "",
            status=",".join(statuses or []), stage=",".join(stages or []),
            verification=verification, generation=generation or None,
        )
        return dcc.send_string(content, filename)

    @app.callback(
        Output("selected-node", "data"),
        Input("graph-3d", "clickData"),
        prevent_initial_call=True,
    )
    def _on_click(click_data):
        if not click_data:
            return no_update
        points = click_data.get("points") or []
        if not points:
            return no_update
        custom = points[0].get("customdata")
        if custom is None:
            return no_update
        return custom

    @app.callback(
        Output("detail-panel", "children"),
        Input("selected-node", "data"),
        Input("reload-token", "data"),
    )
    def _detail(selected, _token):
        md = node_detail_markdown(cache["graph"], selected)
        return dcc.Markdown(md, style={"color": "#e8eaed"})

    return app


def run_dashboard(
    graph_path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8050,
    open_browser: bool = False,
    debug: bool = False,
    view_mode: str = "knowledge",
) -> None:
    app = create_app(graph_path, view_mode=view_mode)
    url = f"http://{host}:{port}"
    print("dashboard")
    print(f"  graph:   {graph_path}")
    print(f"  url:     {url}")
    if open_browser:
        webbrowser.open(url)
    app.run(host=host, port=port, debug=debug)


def _page_style() -> dict:
    return {
        "background": "#0f1115",
        "color": "#e8eaed",
        "fontFamily": "IBM Plex Sans, Segoe UI, sans-serif",
        "minHeight": "100vh",
        "margin": 0,
    }


def _header_style() -> dict:
    return {
        "display": "flex",
        "alignItems": "center",
        "gap": "16px",
        "padding": "14px 18px",
        "borderBottom": "1px solid #2a2e38",
        "background": "#14171e",
    }


def _sidebar_style() -> dict:
    return {
        "width": "340px",
        "padding": "16px",
        "borderRight": "1px solid #2a2e38",
        "overflowY": "auto",
        "background": "#14171e",
        "boxSizing": "border-box",
    }


def _detail_style() -> dict:
    return {"fontSize": "13px", "lineHeight": "1.45"}


def _label_style() -> dict:
    return {"display": "block", "fontSize": "12px", "color": "#8b909a", "marginBottom": "6px"}


def _input_style() -> dict:
    return {
        "width": "100%",
        "padding": "8px 10px",
        "borderRadius": "6px",
        "border": "1px solid #2a2e38",
        "background": "#1a1d24",
        "color": "#e8eaed",
        "boxSizing": "border-box",
    }


def _btn_style() -> dict:
    return {
        "padding": "8px 14px",
        "borderRadius": "6px",
        "border": "1px solid #3a4050",
        "background": "#1e2330",
        "color": "#e8eaed",
        "cursor": "pointer",
    }
