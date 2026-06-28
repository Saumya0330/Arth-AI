"""
अर्थAI — Pipeline Runner (core)

Single place that wraps LangGraph graph calls.
All FastAPI routes import from here — never import graph directly.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from agents.orchestrator import get_graph, create_initial_state  # noqa: E402


def graph():
    return get_graph()


def config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def get_state(thread_id: str) -> dict:
    """Return the current LangGraph state for a thread as a plain dict."""
    snapshot = graph().get_state(config(thread_id))
    state = dict(snapshot.values)
    state["_next_nodes"] = list(snapshot.next)
    return state


def invoke(thread_id: str, update: dict | None = None, as_node: str | None = None):
    """
    Resume a paused graph.
    If update is provided, inject it into state first (for human checkpoints).
    """
    g = graph()
    cfg = config(thread_id)
    if update is not None:
        kwargs = {"as_node": as_node} if as_node else {}
        g.update_state(cfg, update, **kwargs)
    return g.invoke(None, cfg)


def start_pipeline(financial_json: dict, raw_text: str, thread_id: str) -> dict:
    """Kick off a fresh pipeline run from extraction results."""
    g = graph()
    cfg = config(thread_id)
    init = create_initial_state(financial_json, raw_text)
    return g.invoke(init, cfg)
