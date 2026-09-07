"""Stable host-application API for embedding Grapher.

This module is intentionally host-agnostic. External systems may use it as the
supported application boundary instead of writing Grapher state files directly.
All mutations continue through Grapher's canonical mutation machinery.
"""

from grapher.integrations.agent_hub import (
    IntegrationError,
    apply_delta,
    contribute_context,
    export_delta,
    get_context,
    infer_links_context,
    ingest_context,
    init_context,
    link_context,
    list_feedback,
    neighbors_context,
    query_context,
    reindex_context,
)

__all__ = [
    "IntegrationError",
    "apply_delta",
    "contribute_context",
    "export_delta",
    "get_context",
    "infer_links_context",
    "ingest_context",
    "init_context",
    "link_context",
    "list_feedback",
    "neighbors_context",
    "query_context",
    "reindex_context",
]
