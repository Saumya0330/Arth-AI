"""
अर्थAI — Agent 3: Regulatory RAG Retriever

Receives ONLY the auditor-confirmed flags (not all flags, not the full financial JSON).
Queries ChromaDB and generates cited regulatory responses.
Knows nothing about math_validator or compliance_checker internals.
"""

import logging
from agents.state import AuditState

logger = logging.getLogger(__name__)


def run_rag_retriever(state: AuditState) -> AuditState:
    """
    Agent 3 node function.
    Reads state["confirmed_flags"], writes state["flags_with_citations"].
    Only processes flags the auditor confirmed — dismissed flags are dropped.
    """
    from module4.rag import retrieve_regulations, generate_regulatory_response

    confirmed = state.get("confirmed_flags") or []

    if not confirmed:
        logger.info("[RAGRetriever] No confirmed flags to process.")
        return {**state, "flags_with_citations": [], "current_step": "rag_complete"}

    flags_with_citations = []
    for flag in confirmed:
        rule_id = flag.get("rule_id", "?")
        logger.info(f"[RAGRetriever] Retrieving for {rule_id}...")
        passages = retrieve_regulations(flag)
        response = generate_regulatory_response(flag, passages)
        flags_with_citations.append({
            **flag,
            "regulatory_passages": passages,
            "regulatory_response": response,
        })
        logger.info(f"  → {len(passages)} passages retrieved")

    return {
        **state,
        "flags_with_citations": flags_with_citations,
        "current_step": "rag_complete",
    }
