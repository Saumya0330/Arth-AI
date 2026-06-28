"""
अर्थAI — Page 4: Regulatory Rulebook
Shows all embedded regulatory documents, their chunk counts,
and lets the auditor browse/search the knowledge base.
Full RAG chat available on the side.
"""

import streamlit as st
import sys, warnings
from pathlib import Path
from collections import defaultdict

warnings.filterwarnings("ignore")
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(page_title="Rulebook · अर्थAI", page_icon="📚", layout="wide")

# ── Sidebar with RAG chat ──────────────────────────────────────────────────────
with st.sidebar:
    st.title("अर्थAI")
    st.caption("Regulatory Rulebook")
    st.divider()
    st.markdown("""
**Knowledge base** built from:
- CARO 2020
- SA 700 / SA 705
- Any other PDFs you embed

Add more docs by running:
```bash
python generate_embeddings.py
```
    """)
    from app.rag_chat import render_rag_chat
    render_rag_chat()

# ── Main ───────────────────────────────────────────────────────────────────────
st.title("📚 Regulatory Rulebook")
st.caption("All regulatory documents embedded in the knowledge base. "
           "Use the chat in the sidebar to ask questions.")
st.divider()

# Load VectorDB
try:
    from module4.rag import _get_vector_store
    vs = _get_vector_store()
    collection = vs._collection
    total_chunks = collection.count()
except Exception as e:
    st.error(f"Could not load VectorDB: {e}")
    st.info("Run `python generate_embeddings.py` first.")
    st.stop()

# Fetch all metadata
all_meta = collection.get(include=["metadatas"])["metadatas"]

# Group by source document
doc_chunks = defaultdict(list)
for meta in all_meta:
    src = meta.get("source", "unknown")
    page = meta.get("page", "?")
    doc_chunks[src].append(page)

# ── Summary metrics ────────────────────────────────────────────────────────────
m1, m2, m3 = st.columns(3)
m1.metric("Total Chunks", total_chunks)
m2.metric("Documents Embedded", len(doc_chunks))
m3.metric("Embedding Model", "jina-embeddings-v2-base-en")

st.divider()

# ── Per-document cards ─────────────────────────────────────────────────────────
st.subheader("Embedded Documents")
for doc_name, pages in sorted(doc_chunks.items()):
    page_nums = sorted(set(p for p in pages if isinstance(p, int)))
    with st.expander(
        f"📄 **{doc_name}** — {len(pages)} chunks, "
        f"{len(set(pages))} pages",
        expanded=True
    ):
        col_a, col_b = st.columns([1, 2])
        col_a.metric("Chunks", len(pages))
        col_a.metric("Pages covered", len(set(pages)))
        if page_nums:
            col_b.markdown(f"**Pages:** {min(page_nums)} – {max(page_nums)}")
        col_b.markdown(f"**File:** `{doc_name}`")
        col_b.caption(
            "Add more regulatory PDFs by placing them in the Capstone folder "
            "and running `python generate_embeddings.py`."
        )

st.divider()

# ── Semantic search ────────────────────────────────────────────────────────────
st.subheader("🔎 Search the Knowledge Base")
st.caption("Enter a keyword or regulation to find relevant chunks directly.")

query = st.text_input("Search query", placeholder="e.g. related party transactions Section 188")
top_k = st.slider("Number of results", 1, 10, 5)

if query:
    with st.spinner("Searching..."):
        results = vs.similarity_search_with_relevance_scores(query, k=top_k)

    for doc, score in results:
        src  = doc.metadata.get("source", "?")
        page = doc.metadata.get("page", "?")
        with st.expander(
            f"📄 `{src}` p.{page}  —  relevance: **{score:.3f}**",
            expanded=True
        ):
            st.markdown(doc.page_content.strip()[:800])
            if len(doc.page_content) > 800:
                st.caption("(truncated — full chunk is longer)")
