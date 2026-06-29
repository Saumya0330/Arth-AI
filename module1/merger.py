"""
अर्थAI — Module 1: Multi-document merger

Merges multiple partial FinancialStatement dicts (from PDFs and CSVs)
into one unified dict. Strategy: first non-null value wins per field.
Source tags are preserved so auditor can see which file each field came from.
"""

import copy
import logging
from typing import List

logger = logging.getLogger(__name__)


def _deep_merge(base: dict, override: dict, base_sources: dict, override_sources: dict) -> tuple:
    """
    Recursively merge override into base.
    For each leaf field: if base has None/missing, take override's value.
    Returns (merged_dict, merged_sources).
    """
    result  = copy.deepcopy(base)
    sources = dict(base_sources)

    def _walk(b: dict, o: dict, path: str):
        for k, v in o.items():
            full_path = f"{path}.{k}" if path else k
            if isinstance(v, dict):
                if not isinstance(b.get(k), dict):
                    b[k] = {}
                _walk(b[k], v, full_path)
            else:
                # Only override if base value is null/missing
                if b.get(k) is None and v is not None:
                    b[k] = v
                    # Tag source from override if not already in base sources
                    if full_path not in sources and full_path in override_sources:
                        sources[full_path] = override_sources[full_path]

    _walk(result, override, "")
    return result, sources


def merge_financial_dicts(docs: List[dict]) -> dict:
    """
    Merge a list of partial financial dicts into one.
    Each dict should have a '_sources' key and a '_source_file' key.
    Returns a merged dict with combined '_sources'.

    docs = [
        {"company_name": "X", "balance_sheet": {...}, "_sources": {...}, "_source_file": "file1.pdf"},
        {"profit_and_loss": {...}, "_sources": {...}, "_source_file": "file2.csv"},
    ]
    """
    if not docs:
        return {}
    if len(docs) == 1:
        return docs[0]

    merged  = copy.deepcopy(docs[0])
    sources = dict(merged.pop("_sources", {}))

    for doc in docs[1:]:
        doc_sources = doc.get("_sources", {})
        merged, sources = _deep_merge(merged, doc, sources, doc_sources)

    # Track which files contributed
    source_files = [d.get("_source_file", "unknown") for d in docs]
    merged["_sources"]      = sources
    merged["_source_files"] = source_files

    filled = sum(1 for v in sources.values() if v != "unknown")
    logger.info(f"Merged {len(docs)} document(s) → {filled} fields with sources")
    return merged
