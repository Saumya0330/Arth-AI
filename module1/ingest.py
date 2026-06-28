"""
अर्थAI — Module 1: Data Ingestion Pipeline

Entry point for Module 1. Processes all PDFs in data/input/ and writes
one JSON file per document to data/output/.

Usage:
    python -m module1.ingest                    # process all PDFs in data/input/
    python -m module1.ingest path/to/file.pdf   # process a single file

Output JSON shape: see module1/schema.py (FinancialStatement)
"""

import os
import sys
import json
import logging
from pathlib import Path

from module1.extractor import get_full_text
from module1.parser import parse_financial_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent
INPUT_DIR   = BASE_DIR / "data" / "input"
OUTPUT_DIR  = BASE_DIR / "data" / "output"


def process_file(pdf_path: Path) -> dict:
    logger.info(f"Processing: {pdf_path.name}")

    raw_text, method = get_full_text(str(pdf_path))
    logger.info(f"  Extraction method : {method}")
    logger.info(f"  Characters extracted: {len(raw_text):,}")

    fs = parse_financial_text(
        raw_text=raw_text,
        source_file=pdf_path.name,
        extraction_method=method,
    )

    logger.info(f"  Company           : {fs.company_name or 'NOT FOUND'}")
    logger.info(f"  CIN               : {fs.cin or 'NOT FOUND'}")
    logger.info(f"  Financial year    : {fs.financial_year_end or 'NOT FOUND'}")
    logger.info(f"  Extraction conf.  : {fs.extraction_confidence:.0%}")

    if fs.balance_sheet.is_balanced is not None:
        status = "✅ BALANCED" if fs.balance_sheet.is_balanced else "⚠️  UNBALANCED"
        logger.info(f"  Balance sheet     : {status}")

    return fs.to_dict()


def process_directory(input_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(input_dir.glob("*.pdf"))

    if not pdf_files:
        logger.warning(f"No PDFs found in {input_dir}")
        logger.warning("Place company financial PDFs in data/input/ and run again.")
        return

    logger.info(f"Found {len(pdf_files)} PDF(s) in {input_dir}\n")
    results = []

    for pdf_path in pdf_files:
        result = process_file(pdf_path)
        results.append(result)

        out_file = output_dir / (pdf_path.stem + ".json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"  Saved → {out_file.relative_to(BASE_DIR)}\n")

    # Also write a combined file useful for batch processing
    combined_path = output_dir / "_all_financials.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Combined output → {combined_path.relative_to(BASE_DIR)}")
    logger.info(f"\n✅ Module 1 complete — {len(results)} document(s) processed.")


if __name__ == "__main__":
    print("=" * 60)
    print("  अर्थAI — Module 1: Data Ingestion & Preprocessing")
    print("=" * 60 + "\n")

    if len(sys.argv) > 1:
        # Single file mode
        pdf_path = Path(sys.argv[1])
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            sys.exit(1)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        result = process_file(pdf_path)
        out_file = OUTPUT_DIR / (pdf_path.stem + ".json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"Saved → {out_file}")
    else:
        process_directory(INPUT_DIR, OUTPUT_DIR)
