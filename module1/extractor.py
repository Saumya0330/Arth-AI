"""
अर्थAI — Module 1: PDF Extractor

Two-tier extraction:
  Tier 1 — pdfplumber  : text-based PDFs (MCA filings, digital reports)
  Tier 2 — pytesseract : scanned / image-based PDFs (fallback)

A page is sent to OCR if pdfplumber extracts fewer than MIN_CHARS_PER_PAGE
characters from it, indicating a scanned page.

OCR requires the tesseract binary:
    /opt/homebrew/bin/brew install tesseract
"""

import logging
from pathlib import Path

import pdfplumber
from PIL import Image

logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 100   # below this → treat page as scanned


def _check_tesseract():
    """Verify tesseract binary is available; raise a clear error if not."""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        raise EnvironmentError(
            "\nTesseract binary not found.\n"
            "Install it with:  /opt/homebrew/bin/brew install tesseract\n"
            "Then re-run the script."
        )
    return pytesseract


def _page_to_image(page) -> Image.Image:
    """Convert a pdfplumber page to a PIL Image for OCR."""
    return page.to_image(resolution=300).original


def extract_text_from_pdf(pdf_path: str) -> tuple:
    """
    Extract text from each page of a PDF.
    Returns: (pages_text: list[str], method: str)
    method is one of: "text", "ocr", "mixed"
    """
    pages_text = []
    methods_used = set()
    pytesseract = None  # lazy-load only if a scanned page is encountered

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            if len(text.strip()) >= MIN_CHARS_PER_PAGE:
                pages_text.append(text)
                methods_used.add("text")
                logger.debug(f"Page {page_num}: text ({len(text)} chars)")
            else:
                logger.info(f"Page {page_num}: sparse text ({len(text)} chars) → OCR")
                if pytesseract is None:
                    pytesseract = _check_tesseract()
                img = _page_to_image(page)
                ocr_text = pytesseract.image_to_string(img, lang="eng")
                pages_text.append(ocr_text)
                methods_used.add("ocr")

    method = "mixed" if len(methods_used) > 1 else (methods_used.pop() if methods_used else "text")
    return pages_text, method


def extract_tables_from_pdf(pdf_path: str) -> list:
    """
    Extract all tables from a PDF using pdfplumber.
    Returns a flat list of tables, each table being a list of rows.
    """
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)
    return all_tables


def get_full_text(pdf_path: str) -> tuple:
    """
    Convenience wrapper.
    Returns: (full_document_text: str, extraction_method: str)
    """
    pages, method = extract_text_from_pdf(pdf_path)
    return "\n\n".join(pages), method
