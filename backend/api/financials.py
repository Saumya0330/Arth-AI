"""
अर्थAI — Financials API

GET  /api/financials/{id}        — get current financial_json with sources
PUT  /api/financials/{id}        — auditor edits fields → marks auditor_verified
"""

import sys, copy
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

router = APIRouter(prefix="/api/financials", tags=["financials"])


class FieldEdit(BaseModel):
    """One field edit: dotted path + new value (string, number, or null)."""
    path:  str
    value: Optional[Any] = None    # None means clear the field


class FinancialsUpdateRequest(BaseModel):
    edits: List[FieldEdit]


def _set_nested(d: dict, dotted_path: str, value) -> dict:
    keys = dotted_path.split(".")
    node = d
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    # Coerce to float if numeric string, else keep as-is
    if isinstance(value, str) and value.strip() != "":
        try:
            node[keys[-1]] = float(value)
        except ValueError:
            node[keys[-1]] = value
    else:
        node[keys[-1]] = value
    return d


@router.get("/{session_id}")
def get_financials(session_id: str):
    """Return current financial_json + field_sources for a session."""
    from backend.core.pipeline_runner import get_state
    state = get_state(session_id)
    if not state.get("financial_json"):
        raise HTTPException(404, f"Session '{session_id}' not found.")
    return {
        "financial_json": state["financial_json"],
        "field_sources":  state.get("field_sources") or
                          state["financial_json"].get("_sources", {}),
    }


@router.put("/{session_id}")
def update_financials(session_id: str, body: FinancialsUpdateRequest):
    """
    Auditor edits financial fields.
    Each edited field is marked 'auditor_verified' in field_sources.
    Updated state is pushed back into LangGraph so downstream agents
    (RAG, Report Drafter) see the corrected values.
    """
    from backend.core.pipeline_runner import get_state
    from agents.orchestrator import get_graph

    state = get_state(session_id)
    if not state.get("financial_json"):
        raise HTTPException(404, f"Session '{session_id}' not found.")

    updated_fs      = copy.deepcopy(state["financial_json"])
    updated_sources = dict(state.get("field_sources") or
                           updated_fs.get("_sources", {}))
    changed_paths   = []

    for edit in body.edits:
        _set_nested(updated_fs, edit.path, edit.value)
        if edit.value is not None and str(edit.value).strip() != "":
            updated_sources[edit.path] = "auditor_verified"
        else:
            updated_sources.pop(edit.path, None)
        changed_paths.append(edit.path)

    updated_fs["_sources"] = updated_sources

    # Push back into LangGraph state
    graph  = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    graph.update_state(config, {
        "financial_json": updated_fs,
        "field_sources":  updated_sources,
    })

    verified_count = sum(1 for v in updated_sources.values()
                         if v == "auditor_verified")
    return {
        "session_id":      session_id,
        "fields_updated":  changed_paths,
        "auditor_verified_count": verified_count,
        "message": f"{len(changed_paths)} field(s) updated and marked auditor_verified.",
    }
