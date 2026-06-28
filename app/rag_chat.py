"""
अर्थAI — Shared RAG Chat Component

Renders a chat interface in the Streamlit sidebar.
Auditor can ask any question — answered using ChromaDB + Groq.
Import and call render_rag_chat() from any page sidebar.
"""

import streamlit as st
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def _ask_rag(question: str, top_k: int = 4) -> dict:
    """Query VectorDB and generate a cited answer. Returns {answer, sources}."""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    from module4.rag import _get_vector_store
    from groq import Groq

    vs = _get_vector_store()
    results = vs.similarity_search_with_relevance_scores(question, k=top_k)

    passages = []
    for doc, score in results:
        passages.append({
            "content":         doc.page_content.strip()[:500],
            "source":          doc.metadata.get("source", "unknown"),
            "page":            doc.metadata.get("page", "?"),
            "relevance_score": round(score, 3),
        })

    context = "\n\n".join(
        f"[{p['source']}, p.{p['page']} | relevance {p['relevance_score']}]\n{p['content']}"
        for p in passages
    )

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content":
                "You are a regulatory expert on Indian statutory audit standards. "
                "Answer the auditor's question using ONLY the provided regulatory passages. "
                "Always cite the source document and page number. "
                "If the answer is not in the passages, say so clearly."},
            {"role": "user", "content":
                f"Question: {question}\n\nRegulatory passages:\n{context}"},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    return {
        "answer":  response.choices[0].message.content.strip(),
        "sources": passages,
    }


def render_rag_chat():
    """
    Render the RAG chat widget inside the current sidebar context.
    Call this inside a `with st.sidebar:` block.
    """
    st.divider()
    st.markdown("### 💬 Ask the Rulebook")
    st.caption("Ask any audit regulation question. Answered from embedded documents.")

    if "rag_chat_history" not in st.session_state:
        st.session_state["rag_chat_history"] = []

    # Show history (most recent last, max 6 visible)
    history = st.session_state["rag_chat_history"][-6:]
    for turn in history:
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            st.write(turn["answer"])
            if turn.get("sources"):
                with st.expander("Sources", expanded=False):
                    for s in turn["sources"][:3]:
                        st.caption(
                            f"📄 {s['source']} p.{s['page']} "
                            f"(relevance: {s['relevance_score']})"
                        )

    question = st.chat_input("e.g. What does CARO clause 3(ix) require?",
                             key="rag_chat_input")
    if question:
        with st.spinner("Searching rulebook..."):
            try:
                result = _ask_rag(question)
                st.session_state["rag_chat_history"].append({
                    "question": question,
                    "answer":   result["answer"],
                    "sources":  result["sources"],
                })
                st.rerun()
            except Exception as e:
                st.error(f"RAG error: {e}")

    if history:
        if st.button("🗑️ Clear chat", key="clear_rag"):
            st.session_state["rag_chat_history"] = []
            st.rerun()
