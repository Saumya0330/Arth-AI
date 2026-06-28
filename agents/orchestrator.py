"""
अर्थAI — Orchestrator (LangGraph StateGraph)

Uses SqliteSaver so sessions survive app restarts.
Sessions DB: data/arth_ai_sessions.db

Graph:
  math_validator → compliance_checker
       → [HUMAN: review_flags]
       → rag_retriever → report_drafter
       → [HUMAN: review_report]
       → END
"""

import sqlite3
import logging
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from agents.state import AuditState
from agents.math_validator     import run_math_validator
from agents.compliance_checker import run_compliance_checker
from agents.rag_retriever      import run_rag_retriever
from agents.report_drafter     import run_report_drafter

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "data" / "arth_ai_sessions.db"

# Persistent connection — must stay open for the lifetime of the app
# check_same_thread=False is safe here because Streamlit runs single-threaded
_db_conn = None

def _get_checkpointer() -> SqliteSaver:
    global _db_conn
    if _db_conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _db_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        logger.info(f"[Orchestrator] SQLite session DB opened: {DB_PATH}")
    return SqliteSaver(_db_conn)


# ── Human interrupt nodes ──────────────────────────────────────────────────────

def human_review_flags(state: AuditState) -> AuditState:
    """
    HUMAN CHECKPOINT 1: Auditor reviews anomaly flags.
    Graph pauses before this node. Resumed by Streamlit after auditor decisions.
    """
    decisions = state.get("auditor_flag_decisions") or {}
    all_flags = state.get("anomaly_flags") or []

    confirmed = [
        f for f in all_flags
        if decisions.get(f["rule_id"], "confirm") != "dismiss"
    ]
    logger.info(
        f"[Orchestrator] Flags: {len(all_flags)} total → "
        f"{len(confirmed)} confirmed/escalated"
    )
    return {**state, "confirmed_flags": confirmed, "current_step": "flags_reviewed"}


def human_review_report(state: AuditState) -> AuditState:
    """
    HUMAN CHECKPOINT 2: Auditor edits report sections.
    Graph pauses before this node. Resumed after auditor saves edits.
    """
    return {**state, "report_finalised": True, "current_step": "report_finalised"}


# ── Routing ────────────────────────────────────────────────────────────────────

def after_math(state: AuditState) -> str:
    # Math errors surface in the UI but never block the pipeline
    return "compliance_checker"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AuditState)

    graph.add_node("math_validator",      run_math_validator)
    graph.add_node("compliance_checker",  run_compliance_checker)
    graph.add_node("human_review_flags",  human_review_flags)
    graph.add_node("rag_retriever",       run_rag_retriever)
    graph.add_node("report_drafter",      run_report_drafter)
    graph.add_node("human_review_report", human_review_report)

    graph.set_entry_point("math_validator")
    graph.add_conditional_edges("math_validator", after_math,
                                {"compliance_checker": "compliance_checker"})
    graph.add_edge("compliance_checker",  "human_review_flags")
    graph.add_edge("human_review_flags",  "rag_retriever")
    graph.add_edge("rag_retriever",       "report_drafter")
    graph.add_edge("report_drafter",      "human_review_report")
    graph.add_edge("human_review_report", END)

    return graph.compile(
        checkpointer=_get_checkpointer(),
        interrupt_before=["human_review_flags", "human_review_report"],
    )


# ── Singleton ──────────────────────────────────────────────────────────────────

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
        logger.info("[Orchestrator] Graph compiled with SQLite checkpointer.")
    return _graph


# ── Initial state factory ──────────────────────────────────────────────────────

def create_initial_state(financial_json: dict, raw_text: str) -> AuditState:
    return AuditState(
        source_file=financial_json.get("source_file", ""),
        financial_json=financial_json,
        raw_text=raw_text,
        math_report=None,
        anomaly_flags=None,
        auditor_flag_decisions=None,
        confirmed_flags=None,
        flags_with_citations=None,
        report_sections=None,
        report_markdown=None,
        auditor_edits=None,
        report_finalised=False,
        # Carry source audit trail from Module 1+2
        field_sources=financial_json.get("_sources", {}),
        current_step="start",
        errors=[],
    )
