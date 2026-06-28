"""
अर्थAI — RAG Chat & Rulebook API

POST /api/chat              — ask any audit question, answered from VectorDB
GET  /api/rulebook          — list all embedded regulatory documents
POST /api/rulebook/search   — semantic search over VectorDB
"""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

router = APIRouter(tags=["chat & rulebook"])


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    top_k:    int = 4


@router.post("/api/chat")
def rag_chat(body: ChatRequest):
    """
    Auditor asks a free-form question about audit regulations.
    Answers are grounded in the embedded regulatory documents.
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()
    from groq import Groq
    from module4.rag import _get_vector_store

    if not body.question.strip():
        raise HTTPException(400, "Question cannot be empty.")

    vs      = _get_vector_store()
    results = vs.similarity_search_with_relevance_scores(body.question, k=body.top_k)

    passages = [
        {
            "content":         doc.page_content.strip()[:600],
            "source":          doc.metadata.get("source", "unknown"),
            "page":            doc.metadata.get("page", "?"),
            "relevance_score": round(score, 3),
        }
        for doc, score in results
    ]

    context = "\n\n".join(
        f"[{p['source']}, p.{p['page']} | {p['relevance_score']}]\n{p['content']}"
        for p in passages
    )

    client   = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content":
                "You are a regulatory expert on Indian statutory audit standards "
                "(Companies Act 2013, CARO 2020, ICAI Standards on Auditing). "
                "Answer using ONLY the provided passages. Cite source and page. "
                "If the answer is not in the passages, say so clearly."},
            {"role": "user", "content":
                f"Question: {body.question}\n\nPassages:\n{context}"},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    return {
        "answer":   response.choices[0].message.content.strip(),
        "sources":  passages,
        "question": body.question,
    }


# ── Rulebook ───────────────────────────────────────────────────────────────────

@router.get("/api/rulebook")
def list_rulebook():
    """List all embedded regulatory documents with chunk and page counts."""
    from collections import defaultdict
    from module4.rag import _get_vector_store

    vs         = _get_vector_store()
    collection = vs._collection
    all_meta   = collection.get(include=["metadatas"])["metadatas"]

    doc_info = defaultdict(lambda: {"chunks": 0, "pages": set()})
    for meta in all_meta:
        src  = meta.get("source", "unknown")
        page = meta.get("page")
        doc_info[src]["chunks"] += 1
        if isinstance(page, int):
            doc_info[src]["pages"].add(page)

    return {
        "total_chunks": collection.count(),
        "documents": [
            {
                "filename":    src,
                "chunk_count": info["chunks"],
                "page_count":  len(info["pages"]),
                "page_range":  {
                    "min": min(info["pages"]) if info["pages"] else None,
                    "max": max(info["pages"]) if info["pages"] else None,
                },
            }
            for src, info in sorted(doc_info.items())
        ],
    }


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/api/rulebook/search")
def search_rulebook(body: SearchRequest):
    """Semantic search over the regulatory knowledge base."""
    from module4.rag import _get_vector_store

    if not body.query.strip():
        raise HTTPException(400, "Query cannot be empty.")

    vs      = _get_vector_store()
    results = vs.similarity_search_with_relevance_scores(body.query, k=body.top_k)

    return {
        "query":   body.query,
        "results": [
            {
                "content":         doc.page_content.strip(),
                "source":          doc.metadata.get("source", "unknown"),
                "page":            doc.metadata.get("page", "?"),
                "relevance_score": round(score, 3),
            }
            for doc, score in results
        ],
    }
