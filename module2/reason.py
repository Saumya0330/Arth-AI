"""
अर्थAI — Module 2: Entry Point

Reads all JSONs from data/output/ (Module 1 output),
fetches the corresponding raw text, runs LLM completion,
and writes enriched JSONs to data/output/llm/

Usage:
    python -m module2.reason                    # process all Module 1 outputs
    python -m module2.reason path/to/file.json  # process a single JSON
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from module2.reasoning import complete_financial_json_with_sources as complete_financial_json
from module1.extractor import get_full_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent
INPUT_DIR   = BASE_DIR / "data" / "output"        # Module 1 JSONs
LLM_DIR     = BASE_DIR / "data" / "output" / "llm"
PDF_DIR     = BASE_DIR / "data" / "input"


def process_one(json_path: Path):
    with open(json_path) as f:
        partial = json.load(f)

    source_file = partial.get("source_file", "")
    pdf_path = PDF_DIR / source_file

    if not pdf_path.exists():
        logger.warning(f"PDF not found for {source_file}, using text-only mode")
        raw_text = ""
    else:
        logger.info(f"Re-extracting text from: {source_file}")
        raw_text, _ = get_full_text(str(pdf_path))

    logger.info(f"Running LLM completion on: {json_path.name}")
    completed = complete_financial_json(
        partial_json=partial,
        raw_text=raw_text,
        source_file=source_file,
    )

    # Log key results
    logger.info(f"  Company           : {completed.get('company_name', 'N/A')}")
    logger.info(f"  Financial year    : {completed.get('financial_year_end', 'N/A')}")
    logger.info(f"  Confidence        : {completed.get('extraction_confidence', 'N/A')}")

    obs = completed.get("audit_observations", [])
    if obs:
        logger.info(f"  Audit observations ({len(obs)}):")
        for o in obs:
            logger.info(f"    • {o}")

    # Check balance sheet
    bs = completed.get("balance_sheet", {})
    se = bs.get("shareholders_equity", {})
    ncl = bs.get("non_current_liabilities", {})
    cl = bs.get("current_liabilities", {})
    nca = bs.get("non_current_assets", {})
    ca = bs.get("current_assets", {})

    def _sum_section(d):
        return sum(v for v in d.values() if isinstance(v, (int, float)))

    total_eq_liab = _sum_section(se) + _sum_section(ncl) + _sum_section(cl)
    total_assets  = _sum_section(nca) + _sum_section(ca)

    if total_eq_liab and total_assets:
        diff = abs(total_eq_liab - total_assets)
        status = "✅ BALANCED" if diff < 1 else f"⚠️  UNBALANCED (diff: {diff:,.2f})"
        logger.info(f"  Balance sheet     : {status}")

    return completed


def run(target: Path = None):
    LLM_DIR.mkdir(parents=True, exist_ok=True)

    if target:
        json_files = [target]
    else:
        json_files = [
            f for f in sorted(INPUT_DIR.glob("*.json"))
            if not f.name.startswith("_")   # skip _all_financials.json
        ]

    if not json_files:
        logger.warning(f"No JSON files found in {INPUT_DIR}")
        return

    logger.info(f"Found {len(json_files)} file(s) to process\n")

    for json_path in json_files:
        try:
            completed = process_one(json_path)
            out_path = LLM_DIR / json_path.name
            with open(out_path, "w") as f:
                json.dump(completed, f, indent=2, default=str)
            logger.info(f"  Saved → data/output/llm/{json_path.name}\n")
        except Exception as e:
            logger.error(f"Failed on {json_path.name}: {e}")

    logger.info(f"✅ Module 2 complete.")


if __name__ == "__main__":
    print("=" * 60)
    print("  अर्थAI — Module 2: LLM Reasoning")
    print("=" * 60 + "\n")

    if len(sys.argv) > 1:
        run(target=Path(sys.argv[1]))
    else:
        run()
