"""
अर्थAI — Module 5: Entry Point

Reads RAG-enriched JSONs from data/output/rag/,
generates the audit report draft, and writes:
  - data/output/reports/*.json     (structured, machine-readable)
  - data/output/reports/*.md       (human-readable, auditor-editable)

Usage:
    python -m module5.generate                    # process all
    python -m module5.generate path/to/file.json  # single file
"""

import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from module5.report_generator import generate_report
from module5.renderer import render_markdown

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent.parent
INPUT_DIR   = BASE_DIR / "data" / "output" / "rag"
REPORT_DIR  = BASE_DIR / "data" / "output" / "reports"


def run(target: Path = None):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if target:
        json_files = [target]
    else:
        json_files = sorted(INPUT_DIR.glob("*.json"))

    if not json_files:
        logger.warning(f"No JSON files in {INPUT_DIR}. Run Module 4 first.")
        return

    logger.info(f"Found {len(json_files)} file(s)\n")

    for json_path in json_files:
        try:
            with open(json_path) as f:
                fs = json.load(f)

            # Generate structured report
            report = generate_report(fs)

            # Save JSON version
            json_out = REPORT_DIR / json_path.name
            with open(json_out, "w") as f:
                json.dump(report, f, indent=2, default=str)

            # Save markdown version
            md_out = REPORT_DIR / (json_path.stem + ".md")
            md_content = render_markdown(report)
            with open(md_out, "w") as f:
                f.write(md_content)

            company = report.get("company_name", json_path.stem)
            opinion = report.get("report_sections", {}).get("overall_opinion_type", "?")
            logger.info(f"  Company   : {company}")
            logger.info(f"  Opinion   : {opinion.upper()}")
            logger.info(f"  JSON  → data/output/reports/{json_path.name}")
            logger.info(f"  Report→ data/output/reports/{json_path.stem}.md\n")

        except Exception as e:
            logger.error(f"Failed on {json_path.name}: {e}")
            raise

    logger.info("✅ Module 5 complete — audit report drafts ready for review.")


if __name__ == "__main__":
    print("=" * 60)
    print("  अर्थAI — Module 5: Report Generation")
    print("=" * 60 + "\n")

    if len(sys.argv) > 1:
        run(target=Path(sys.argv[1]))
    else:
        run()
