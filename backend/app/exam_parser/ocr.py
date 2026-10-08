"""
ocr.py
======
Stage 2 (fallback) of the exam parser pipeline.

This module handles ONE job:
    When a PDF page has no usable embedded text,
    render it as an image and run Tesseract OCR on it.

It does NOT run on every page — only pages where pdf_reader
returned has_text = False.

It does NOT normalise or clean the OCR output.
Normalisation happens in normalizer.py.

It does NOT parse questions or extract metadata.

Flow:
    PDF page (no embedded text)
         |
         v
    PyMuPDF renders page → pixel image (like a screenshot)
         |
         v
    PIL converts pixels → Image object
         |
         v
    Tesseract OCR reads image → raw string
         |
         v
    Return raw OCR text

Output per page:
    {
        "page_number": 2,
        "ocr_text": "Q1. Explain normalization...",
        "source": "ocr"        <- so downstream knows this came from OCR
    }

Why keep source="ocr"?
    OCR text tends to have more errors than embedded text.
    Member 4 (NLP cleaning) may want to apply extra cleaning
    to OCR-sourced text. Flagging the source makes that easy.
"""

import logging
import os
from typing import Optional

import pymupdf      # renders PDF pages to images
import pytesseract  # calls Tesseract binary
from PIL import Image
from dotenv import load_dotenv

# ── Load .env robustly ─────────────────────────────────────────────────────────
# Walk up from this file's location until we find a .env file.
# This works regardless of where the script is called from.
def _find_and_load_dotenv() -> None:
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):   # search up to 6 levels up
        candidate = os.path.join(current, ".env")
        if os.path.exists(candidate):
            load_dotenv(candidate)
            return
        current = os.path.dirname(current)
    # If not found, load_dotenv() with no args tries CWD — last resort
    load_dotenv()

_find_and_load_dotenv()

# ── Logger ─────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)


# ── Tesseract configuration ────────────────────────────────────────────────────

def _configure_tesseract() -> None:
    """
    Tell pytesseract where the Tesseract binary lives.

    Why do this at runtime instead of hardcoding?
    - Different machines have different install paths
    - The path is stored in .env so it's easy to change per developer
    - If TESSERACT_PATH is not set, we fall back to system PATH

    This function is called once when the module loads.
    """
    tess_path = os.getenv("TESSERACT_PATH", "")
    if tess_path and os.path.exists(tess_path):
        pytesseract.pytesseract.tesseract_cmd = tess_path
        logger.debug(f"Tesseract path set to: {tess_path}")
    else:
        # Trust the system PATH — works if Tesseract was added to PATH
        # during installation or on Linux/Mac
        logger.debug("TESSERACT_PATH not set, using system PATH")


# Call it immediately when this module is imported
_configure_tesseract()


# ── Constants ──────────────────────────────────────────────────────────────────

# Zoom factor when rendering PDF pages to images.
#
# Why zoom? Tesseract works best on high-resolution images.
# A standard PDF page is 72 DPI. At zoom=2, we get 144 DPI (2x).
# At zoom=3, we get 216 DPI (3x).
#
# Rule of thumb:
#   - zoom=2 → fast, decent accuracy for clean prints
#   - zoom=3 → slower, better accuracy for messy/small text
#   - zoom=4 → very slow, for extremely poor quality scans
#
# We default to 3 which gives good accuracy for exam papers.
DEFAULT_ZOOM = 3

# Tesseract page segmentation mode (PSM).
# PSM 6 = "Assume a single uniform block of text."
# This works well for exam papers where text flows top to bottom.
# Other useful values:
#   PSM 3  = fully automatic (default)
#   PSM 11 = sparse text (for papers with complex layouts)
TESSERACT_CONFIG = "--psm 6"


# ── Main OCR function ──────────────────────────────────────────────────────────

def ocr_page(pdf_path: str, page_number: int, zoom: int = DEFAULT_ZOOM) -> dict:
    """
    Run OCR on a single page of a PDF.

    This is the function called by parser.py when pdf_reader tells us
    a page has no embedded text.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.
    page_number : int
        The 1-indexed page number to OCR.
        (We use 1-indexed everywhere to match what pdf_reader returns.)
    zoom : int, optional
        Zoom factor for rendering. Higher = better quality but slower.
        Default is 3 (good balance for exam papers).

    Returns
    -------
    dict with keys:
        - page_number (int)  : The page number (same as input)
        - ocr_text    (str)  : Raw OCR output. Empty string if OCR fails.
        - source      (str)  : Always "ocr" so downstream knows the origin.

    Notes
    -----
    - This function NEVER raises an exception. If OCR fails for any reason,
      it returns an empty string and logs the error.
    - The text returned is raw — no spelling correction, no cleaning.
    """
    logger.info(f"Running OCR on page {page_number} of '{pdf_path}'")

    # Always return this structure, even if we fail
    result = {
        "page_number": page_number,
        "ocr_text":    "",
        "source":      "ocr",
    }

    try:
        # Step 1: Render the PDF page to a pixel image using PyMuPDF
        image = _render_page_to_image(pdf_path, page_number, zoom)

        if image is None:
            logger.warning(f"Could not render page {page_number} — returning empty")
            return result

        # Step 2: Run Tesseract OCR on that image
        raw_text = _run_tesseract(image, page_number)

        result["ocr_text"] = raw_text
        logger.info(
            f"OCR complete on page {page_number}: "
            f"{len(raw_text)} chars extracted"
        )

    except Exception as e:
        # Never crash — just log and return empty
        logger.error(
            f"OCR failed on page {page_number} of '{pdf_path}': {e}",
            exc_info=True   # includes the full stack trace in the log
        )

    return result


def ocr_pdf(pdf_path: str, pages_to_ocr: list[int], zoom: int = DEFAULT_ZOOM) -> list[dict]:
    """
    Run OCR on multiple pages of the same PDF.

    This is a convenience wrapper that calls ocr_page() for each
    page number in the list.

    Called by parser.py after pdf_reader identifies which pages need OCR.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.
    pages_to_ocr : list[int]
        List of 1-indexed page numbers that need OCR.
        Typically the pages where pdf_reader returned has_text=False.
    zoom : int, optional
        Render zoom factor. Default is 3.

    Returns
    -------
    list[dict]
        One dict per page, same structure as ocr_page() returns.

    Example
    -------
    # After pdf_reader runs:
    pages = extract_pages("paper.pdf")
    needs_ocr = [p["page_number"] for p in pages if not p["has_text"]]

    # Then:
    ocr_results = ocr_pdf("paper.pdf", needs_ocr)
    """
    logger.info(
        f"Starting batch OCR: {len(pages_to_ocr)} page(s) from '{pdf_path}'"
    )

    results = []
    for page_num in pages_to_ocr:
        result = ocr_page(pdf_path, page_num, zoom)
        results.append(result)

    return results


# ── Internal helpers ───────────────────────────────────────────────────────────

def _render_page_to_image(
    pdf_path: str,
    page_number: int,
    zoom: int
) -> Optional[Image.Image]:
    """
    Use PyMuPDF to render one PDF page into a PIL Image.

    Think of this as "taking a screenshot" of a single page.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF.
    page_number : int
        1-indexed page number.
    zoom : int
        Zoom/scale factor. zoom=3 means 3x the base resolution.

    Returns
    -------
    PIL.Image.Image or None
        The rendered page as a colour image, or None if rendering fails.

    How it works (step by step):
    1. pymupdf.open() loads the PDF
    2. load_page(page_number - 1) loads the specific page
       (PyMuPDF uses 0-indexed pages internally)
    3. pymupdf.Matrix(zoom, zoom) creates a scaling transform
       zoom=3 means "make every pixel 3x bigger"
    4. page.get_pixmap(matrix=mat) renders the page into a pixel buffer
    5. Image.frombytes() converts the raw pixel bytes into a PIL Image
       that pytesseract can read
    """
    try:
        doc = pymupdf.open(pdf_path)

        # PyMuPDF uses 0-indexed pages — convert our 1-indexed page_number
        page_index = page_number - 1

        if page_index < 0 or page_index >= len(doc):
            logger.warning(
                f"Page {page_number} is out of range "
                f"(PDF has {len(doc)} pages)"
            )
            doc.close()
            return None

        page = doc.load_page(page_index)

        # Create the zoom matrix — this is what makes the image high-res
        # Matrix(3, 3) means scale x by 3 and y by 3
        mat = pymupdf.Matrix(zoom, zoom)

        # Render to a pixmap (raw pixel buffer)
        # colorspace=pymupdf.csRGB means we want colour (not greyscale)
        pix = page.get_pixmap(matrix=mat, colorspace=pymupdf.csRGB)

        doc.close()

        # Convert the raw pixel bytes to a PIL Image
        # pix.samples = raw bytes of pixel data
        # pix.width, pix.height = image dimensions
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        logger.debug(
            f"Rendered page {page_number}: "
            f"{image.width}x{image.height} px (zoom={zoom}x)"
        )
        return image

    except Exception as e:
        logger.error(f"Render failed for page {page_number}: {e}")
        return None


def _run_tesseract(image: Image.Image, page_number: int) -> str:
    """
    Pass a PIL Image to Tesseract and get back the recognised text.

    Parameters
    ----------
    image : PIL.Image.Image
        The rendered page image.
    page_number : int
        Used only for logging.

    Returns
    -------
    str
        The raw OCR text. Empty string if Tesseract fails or finds nothing.

    Notes
    -----
    - lang="eng" means English language model.
      If your papers have other languages (Hindi etc.), add them:
      lang="eng+hin"
    - config=TESSERACT_CONFIG controls the page segmentation mode.
    - We strip leading/trailing whitespace but do NOT clean further.
      Cleaning is normalizer.py's job.
    """
    try:
        raw_text = pytesseract.image_to_string(
            image,
            lang="eng",
            config=TESSERACT_CONFIG
        )

        # Strip surrounding whitespace but keep internal structure
        raw_text = raw_text.strip()

        if not raw_text:
            logger.warning(
                f"Tesseract returned empty text for page {page_number}. "
                "The scan may be too dark, blurry, or rotated."
            )

        return raw_text

    except pytesseract.TesseractNotFoundError:
        logger.error(
            "Tesseract binary not found! "
            "Set TESSERACT_PATH correctly in backend/.env"
        )
        return ""
    except Exception as e:
        logger.error(f"Tesseract failed on page {page_number}: {e}")
        return ""


# ── Utility: check Tesseract is reachable ─────────────────────────────────────

def is_tesseract_available() -> bool:
    """
    Check whether Tesseract is installed and reachable.

    Returns True/False without raising any exceptions.
    Called by the health-check endpoint and check_env.py.
    """
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
