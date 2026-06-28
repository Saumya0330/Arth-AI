"""
अर्थAI — Orchestrator (LangGraph StateGraph)

Defines the pipeline graph and manages all transitions.
Human interrupt nodes pause the graph at auditor checkpoints.

Graph structure:
  extract → math_validator → compliance_checker
                                    ↓
                          [HUMAN: review_flags]
                                    ↓
                            rag_retriever
                                    ↓
                          [HUMAN: review_citations]
                                    ↓
                            report_drafter
                                    ↓
                          [HUMAN: review_report]
                                    ↓
                                  END
"""

import json
import logging
from pathlib import Path
from typing import Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.state import AuditState
from agents.math_validator     import run_math_validator
from agents.compliance_checker import run_compliance_checker
from agents.rag_retriever      import run_rag_retriever
from agents.report_drafter     import run_report_drafter

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


# ── Human interrupt nodes (just pass state through — UI pauses here) ──────────

def human_review_flags(state: AuditState) -> AuditState:
    """
    HUMAN CHECKPOINT 1: Auditor reviews anomaly flags.
    This node is interrupted by LangGraph before execution.
    When resumed, auditor_flag_decisions must be set in the state.
    """
    decisions = state.get("auditor_flag_decisions") or {}
    all_flags = state.get("anomaly_flags") or []

    # Keep only flags auditor confirmed or escalated (not dismissed)
    confirmed = [
        f for f in all_flags
        if decisions.get(f["rule_id"], "confirm") != "dismiss"
    ]

    logger.info(
        f"[Orchestrator] Flag review: {len(all_flags)} total, "
        f"{len(confirmed)} confirmed/escalated"
    )
    return {
        **state,
        "confirmed_flags": confirmed,
        "current_step": "flags_reviewed",
    }


def human_review_report(state: AuditState) -> AuditState:
    """
    HUMAN CHECKPOINT 2: Auditor edits report sections.
    When resumed, auditor_edits must be set in the state.
    """
    return {
        **state,
        "report_finalised": True,
        "current_step": "report_finalised",
    }


# ── Conditional edge: should we halt after math validation? ───────────────────

def should_continue_after_math(state: AuditState) -> str:
    """
    If math has critical errors AND no auditor override, pause for review.
    Otherwise proceed to compliance checking.
    (For now always continues — math errors are surfaced but don't block pipeline.)
    """
    return "compliance_checker"


# ── Build the graph ────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AuditState)

    # Add all nodes
    graph.add_node("math_validator",      run_math_validator)
    graph.add_node("compliance_checker",  run_compliance_checker)
    graph.add_node("human_review_flags",  human_review_flags)
    graph.add_node("rag_retriever",       run_rag_retriever)
    graph.add_node("report_drafter",      run_report_drafter)
    graph.add_node("human_review_report", human_review_report)

    # Entry point
    graph.set_entry_point("math_validator")

    # Edges
    graph.add_conditional_edges(
        "math_validator",
        should_continue_after_math,
        {"compliance_checker": "compliance_checker"},
    )
    graph.add_edge("compliance_checker",  "human_review_flags")
    graph.add_edge("human_review_flags",  "rag_retriever")
    graph.add_edge("rag_retriever",       "report_drafter")
    graph.add_edge("report_drafter",      "human_review_report")
    graph.add_edge("human_review_report", END)

    # Interrupt before human nodes — graph pauses here waiting for auditor
    memory = MemorySaver()
    return graph.compile(
        checkpointer=memory,
        interrupt_before=["human_review_flags", "human_review_report"],
    )


# ── Convenience runner used by Streamlit ──────────────────────────────────────

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
        current_step="start",
        errors=[],
    )


# ── Singleton graph instance ───────────────────────────────────────────────────
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
