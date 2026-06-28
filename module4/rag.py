"""
अर्थAI — Module 4: Regulatory RAG Pipeline

For each anomaly flag from Module 3, this module:
  1. Constructs a semantic search query from the flag's rule + description
  2. Queries the ChromaDB vector store (built from CARO 2020, SA 700/705,
     and all other regulatory PDFs you add)
  3. Returns the top-k most relevant regulatory passages
  4. Calls the LLM to produce a cited regulatory response:
     "This anomaly relates to [Clause X] of [Regulation Y] which states..."

The VectorDB automatically includes ALL documents embedded via generate_embeddings.py
— no changes needed here when you add more regulatory PDFs.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parent.parent
CHROMA_PATH   = str(BASE_DIR / "VectorDB")
TOP_K         = 5      # number of regulatory chunks to retrieve per flag
GROQ_MODEL    = "llama-3.3-70b-versatile"
TEMPERATURE   = 0.1


# ── Vector store (shared across all calls — loaded once) ──────────────────────

_vector_store = None

def _get_vector_store():
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    import torch
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma

    if not Path(CHROMA_PATH).exists():
        raise FileNotFoundError(
            f"VectorDB not found at {CHROMA_PATH}.\n"
            f"Run generate_embeddings.py first."
        )

    device = "mps" if torch.backends.mps.is_available() else \
             "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading VectorDB on: {device}")

    embeddings = HuggingFaceEmbeddings(
        model_name="jinaai/jina-embeddings-v2-base-en",
        model_kwargs={"device": device, "trust_remote_code": True},
        encode_kwargs={"normalize_embeddings": True},
    )

    _vector_store = Chroma(
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH,
    )
    doc_count = _vector_store._collection.count()
    logger.info(f"VectorDB loaded — {doc_count} chunks across all regulatory documents")
    return _vector_store


# ── LLM client ─────────────────────────────────────────────────────────────────

def _get_groq_client():
    from groq import Groq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not found in .env")
    return Groq(api_key=api_key)


# ── Query builder — turns an anomaly flag into a search query ─────────────────

# Maps rule_id prefixes to regulatory search hints
RULE_QUERY_HINTS = {
    "BS-001": "balance sheet Schedule III Companies Act 2013 format equity liabilities assets",
    "LR-001": "current ratio liquidity going concern auditor responsibility SA 570",
    "LR-002": "cash adequacy liquidity risk audit procedures",
    "PR-001": "going concern losses accumulated audit report qualification SA 570 SA 705",
    "PR-002": "profit after tax extraction audit evidence",
    "DT-001": "debt equity ratio borrowings CARO 2020 clause default loans",
    "DT-002": "finance costs interest expense borrowings off balance sheet CARO",
    "BF-001": "Benford law fraud detection unusual transactions audit sampling",
    "EC-001": "employee benefits expense related party transactions SA 550 CARO",
}


def _build_search_query(flag: dict) -> str:
    rule_id = flag.get("rule_id", "")
    description = flag.get("description", "")
    field = flag.get("field", "")

    # Get hint for this rule prefix
    prefix = rule_id.split("-")[0] + "-" + rule_id.split("-")[1] if "-" in rule_id else rule_id
    hint = RULE_QUERY_HINTS.get(rule_id, RULE_QUERY_HINTS.get(prefix, ""))

    query = f"{description} {field} {hint}".strip()
    return query[:500]  # ChromaDB query length limit


# ── RAG retrieval ──────────────────────────────────────────────────────────────

def retrieve_regulations(flag: dict, top_k: int = TOP_K) -> list:
    """
    Retrieve top_k regulatory passages relevant to an anomaly flag.
    Returns list of dicts: {content, source, page, relevance_score}
    """
    vs = _get_vector_store()
    query = _build_search_query(flag)

    results = vs.similarity_search_with_relevance_scores(query, k=top_k)

    passages = []
    for doc, score in results:
        passages.append({
            "content": doc.page_content.strip(),
            "source": doc.metadata.get("source", "unknown"),
            "page": doc.metadata.get("page", "?"),
            "relevance_score": round(score, 4),
        })
    return passages


# ── LLM: generate cited regulatory response ───────────────────────────────────

RAG_SYSTEM_PROMPT = """You are a senior Chartered Accountant AI specializing in Indian statutory audits.

Given an anomaly detected in a company's financial statements and relevant regulatory passages,
your task is to:
1. Identify the specific clause, section, or standard that applies
2. Explain what the regulation requires
3. State what the auditor must do or verify
4. Keep your response concise and citation-precise

Always cite in the format: [Source Document, Page X] or [Clause X.Y, Standard Name]"""

RAG_USER_PROMPT = """ANOMALY DETECTED:
Rule ID    : {rule_id}
Severity   : {severity}
Field      : {field}
Description: {description}

RETRIEVED REGULATORY PASSAGES:
{passages}

Based on the above regulatory passages, provide:
1. The specific clause/section that governs this anomaly
2. What the regulation requires in this situation
3. Recommended audit procedure for the auditor
4. Draft audit observation sentence (1-2 lines) to include in the report"""


def generate_regulatory_response(flag: dict, passages: list) -> str:
    """Call LLM with flag + retrieved passages to get a cited regulatory response."""
    if not passages:
        return "No relevant regulatory passages found in the knowledge base for this flag."

    client = _get_groq_client()

    formatted_passages = ""
    for i, p in enumerate(passages, 1):
        formatted_passages += (
            f"\n[{i}] Source: {p['source']}, Page {p['page']} "
            f"(relevance: {p['relevance_score']:.2f})\n"
            f"{p['content'][:600]}\n"
            f"{'─'*60}"
        )

    user_msg = RAG_USER_PROMPT.format(
        rule_id=flag.get("rule_id", ""),
        severity=flag.get("severity", ""),
        field=flag.get("field", ""),
        description=flag.get("description", ""),
        passages=formatted_passages,
    )

    response = _get_groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=TEMPERATURE,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


# ── Main: process all flags in a financial statement ──────────────────────────

def process_anomaly_flags(fs: dict) -> dict:
    """
    For every anomaly flag in fs["anomaly_flags"], retrieve regulations
    and generate a cited response. Returns enriched fs dict.
    """
    flags = fs.get("anomaly_flags", [])
    if not flags:
        logger.info("No anomaly flags to process.")
        return fs

    logger.info(f"Processing {len(flags)} anomaly flag(s) through RAG pipeline...")

    enriched_flags = []
    for flag in flags:
        rule_id = flag.get("rule_id", "?")
        logger.info(f"  Retrieving regulations for {rule_id}...")

        passages = retrieve_regulations(flag)
        logger.info(f"    → {len(passages)} passages retrieved from VectorDB")

        regulatory_response = generate_regulatory_response(flag, passages)

        enriched_flags.append({
            **flag,
            "regulatory_passages": passages,
            "regulatory_response": regulatory_response,
        })

    fs["anomaly_flags"] = enriched_flags
    return fs
