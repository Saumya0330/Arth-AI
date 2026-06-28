"""
अर्थAI — Agent State Schema

This TypedDict is the ONLY thing that flows between nodes in the LangGraph graph.
Each agent reads from it and writes its results back to it.
Agents never call each other directly — the orchestrator manages all transitions.
"""

from typing import TypedDict, Optional, List, Dict, Any


class AuditState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    source_file:        str             # original PDF filename
    financial_json:     Dict[str, Any]  # Module 1+2 output (LLM-completed)
    raw_text:           str             # full OCR/extracted text from PDF

    # ── Agent 1: Math Validator output ────────────────────────────────────────
    math_report:        Optional[Dict]  # { checks: [...], has_critical_errors: bool }

    # ── Agent 2: Compliance Checker output ───────────────────────────────────
    anomaly_flags:      Optional[List[Dict]]  # raw flags before auditor review

    # ── Auditor checkpoint: flag review ──────────────────────────────────────
    auditor_flag_decisions: Optional[Dict[str, str]]  # { rule_id: "confirm"|"dismiss"|"escalate" }
    confirmed_flags:    Optional[List[Dict]]  # only flags auditor confirmed

    # ── Agent 3: RAG Retriever output ─────────────────────────────────────────
    flags_with_citations: Optional[List[Dict]]  # confirmed flags + regulatory passages

    # ── Agent 4: Report Drafter output ────────────────────────────────────────
    report_sections:    Optional[Dict]  # structured report JSON
    report_markdown:    Optional[str]   # rendered markdown

    # ── Auditor checkpoint: report review ────────────────────────────────────
    auditor_edits:      Optional[Dict[str, str]]  # section_key → edited text
    report_finalised:   bool

    # ── Pipeline metadata ─────────────────────────────────────────────────────
    current_step:       str             # which node last ran
    errors:             List[str]       # non-fatal errors accumulated
