"""
अर्थAI — Module 3: Entry Point

Reads LLM-completed JSONs from data/output/llm/,
runs all anomaly checks, and writes enriched JSONs
with an "anomaly_flags" array to data/output/anomaly/

Usage:
    python -m module3.detect                    # process all LLM outputs
    python -m module3.detect path/to/file.json  # single file
"""

import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from module3.anomaly import run_all_checks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent.parent
INPUT_DIR    = BASE_DIR / "data" / "output" / "llm"
ANOMALY_DIR  = BASE_DIR / "data" / "output" / "anomaly"

SEVERITY_EMOJI = {"critical": "🔴", "warning": "🟡", "info": "🔵"}


def process_one(json_path: Path) -> dict:
    with open(json_path) as f:
        fs = json.load(f)

    company = fs.get("company_name", json_path.stem)
    logger.info(f"Running anomaly detection: {company}")

    flags = run_all_checks(fs)

    critical = [f for f in flags if f["severity"] == "critical"]
    warnings  = [f for f in flags if f["severity"] == "warning"]
    info      = [f for f in flags if f["severity"] == "info"]

    logger.info(f"  🔴 Critical : {len(critical)}")
    logger.info(f"  🟡 Warnings : {len(warnings)}")
    logger.info(f"  🔵 Info     : {len(info)}")

    fs["anomaly_flags"] = flags
    fs["anomaly_summary"] = {
        "total": len(flags),
        "critical": len(critical),
        "warning": len(warnings),
        "info": len(info),
    }
    return fs


def run(target: Path = None):
    ANOMALY_DIR.mkdir(parents=True, exist_ok=True)

    if target:
        json_files = [target]
    else:
        json_files = sorted(INPUT_DIR.glob("*.json"))

    if not json_files:
        logger.warning(f"No JSON files in {INPUT_DIR}. Run Module 2 first.")
        return

    logger.info(f"Found {len(json_files)} file(s)\n")

    for json_path in json_files:
        try:
            result = process_one(json_path)
            out_path = ANOMALY_DIR / json_path.name
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            logger.info(f"  Saved → data/output/anomaly/{json_path.name}\n")
        except Exception as e:
            logger.error(f"Failed on {json_path.name}: {e}")

    logger.info("✅ Module 3 complete.")


if __name__ == "__main__":
    print("=" * 60)
    print("  अर्थAI — Module 3: Anomaly Detection")
    print("=" * 60 + "\n")

    if len(sys.argv) > 1:
        run(target=Path(sys.argv[1]))
    else:
        run()
