"""
अर्थAI — Module 4: Entry Point

Reads anomaly-enriched JSONs from data/output/anomaly/,
runs the RAG pipeline on each flag, and writes final
cited JSONs to data/output/rag/

Usage:
    python -m module4.retrieve                    # process all
    python -m module4.retrieve path/to/file.json  # single file
"""

import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from module4.rag import process_anomaly_flags

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent
INPUT_DIR   = BASE_DIR / "data" / "output" / "anomaly"
RAG_DIR     = BASE_DIR / "data" / "output" / "rag"


def run(target: Path = None):
    RAG_DIR.mkdir(parents=True, exist_ok=True)

    if target:
        json_files = [target]
    else:
        json_files = sorted(INPUT_DIR.glob("*.json"))

    if not json_files:
        logger.warning(f"No JSON files in {INPUT_DIR}. Run Module 3 first.")
        return

    logger.info(f"Found {len(json_files)} file(s)\n")

    for json_path in json_files:
        try:
            with open(json_path) as f:
                fs = json.load(f)

            company = fs.get("company_name", json_path.stem)
            logger.info(f"Processing: {company}\n")

            enriched = process_anomaly_flags(fs)

            out_path = RAG_DIR / json_path.name
            with open(out_path, "w") as f:
                json.dump(enriched, f, indent=2, default=str)

            logger.info(f"Saved → data/output/rag/{json_path.name}\n")

        except Exception as e:
            logger.error(f"Failed on {json_path.name}: {e}")
            raise

    logger.info("✅ Module 4 complete.")


if __name__ == "__main__":
    print("=" * 60)
    print("  अर्थAI — Module 4: Regulatory RAG")
    print("=" * 60 + "\n")

    if len(sys.argv) > 1:
        run(target=Path(sys.argv[1]))
    else:
        run()
