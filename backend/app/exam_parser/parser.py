"""
parser.py
=========
Stage 6 (final) of the exam parser pipeline.

This is the main orchestrator — it calls all the other modules
in the right order and returns a complete ParsedDocument.

This is the ONLY file that other parts of the project (the API,
the database layer) should import from directly.

The full pipeline this file orchestrates:

    PDF file
        |
        v
    [pdf_reader.py]   Extract embedded text per page
        |
        v
    [ocr.py]          OCR fallback for pages with no text layer
        |
        v
    [normalizer.py]   Clean up whitespace and formatting artifacts
        |
        v
    [metadata.py]     Extract document-level year and exam_type
        |
        v
    [segmenter.py]    Split normalized text into question segments
        |
        v
    [metadata.py]     Extract per-question marks and is_compulsory
        |
        v
    [models.py]       Build validated Question objects
        |
        v
    ParsedDocument    Ready for DB storage or API response

Member 3's work ends here.
Member 4 picks up the Question records and fills:
    cleaned_text, topic_id, repeat_group_id

Public API:
    parse_question_paper(pdf_path, document_id)  → ParsedDocument
    parse_to_json(pdf_path, document_id)         → dict (for JSON/API)
    parse_to_json_file(pdf_path, document_id, output_path)  → saves JSON
"""

import json
import logging
import os
from typing import Optional

from .pdf_reader  import extract_pages, get_pdf_page_count
from .ocr         import ocr_page
from .normalizer  import normalize
from .segmenter   import segment_all_pages
from .metadata    import (
    extract_document_metadata,
    enrich_questions_with_metadata,
)
from .models      import make_question, ParsedDocument, Question

# ── Logging setup ──────────────────────────────────────────────────────────────
# Configure logging for the whole exam_parser package.
# In development, set ENV=development in .env to see DEBUG messages.
# In production, only WARNING and above will be shown.

def _setup_logging() -> None:
    env = os.getenv("ENV", "development")
    level = logging.DEBUG if env == "development" else logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

_setup_logging()
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def parse_question_paper(
    pdf_path: str,
    document_id: int,
    global_marks: Optional[int] = None,
) -> ParsedDocument:
    """
    Parse a question paper PDF into structured Question records.

    This is the single function to call. It runs the complete pipeline.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file. Can be absolute or relative.
    document_id : int
        The document ID assigned by Member 6's ingestion system.
        All questions from this PDF will share this document_id.
    global_marks : int or None
        Optional: if you know all questions carry the same marks
        (e.g. from a section instruction "each question carries 5 marks"),
        pass that value here. Questions with inline marks will still
        use their own marks — this is only the fallback.

    Returns
    -------
    ParsedDocument
        A validated Pydantic model containing:
            - document_id
            - year, exam_type  (from document header)
            - total_pages
            - questions[]      (list of Question objects)

    Raises
    ------
    FileNotFoundError
        If the PDF file does not exist at pdf_path.

    Notes
    -----
    - The parser NEVER crashes due to missing metadata.
      If year/marks/section cannot be found, they are set to None.
    - If a page has no text layer, OCR is used automatically.
    - If OCR also fails, that page is skipped with a log warning.

    Example
    -------
        result = parse_question_paper("data/papers/dbms_2025.pdf", document_id=101)
        print(result.model_dump_json(indent=2))
    """
    logger.info(f"━━━ Starting parse: '{pdf_path}' (document_id={document_id}) ━━━")

    # ── Step 0: validate the file exists ──────────────────────────────────
    if not os.path.exists(pdf_path):
        logger.error(f"PDF not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    total_pages = get_pdf_page_count(pdf_path) or 0
    logger.info(f"PDF has {total_pages} page(s)")

    # ── Step 1: extract text from each page ───────────────────────────────
    logger.info("Step 1: Extracting embedded text...")
    raw_pages = _extract_all_page_text(pdf_path)

    if not raw_pages:
        logger.warning("No pages could be read from the PDF.")
        return ParsedDocument(document_id=document_id, total_pages=total_pages)

    # ── Step 2: normalize each page's text ────────────────────────────────
    logger.info("Step 2: Normalizing text...")
    normalized_pages = _normalize_pages(raw_pages)

    # ── Step 3: extract document-level metadata from first 2 pages ────────
    logger.info("Step 3: Extracting document metadata...")
    header_text = _get_header_text(normalized_pages, max_pages=2)
    doc_meta = extract_document_metadata(header_text)
    logger.info(
        f"  year={doc_meta['year']}, exam_type={doc_meta['exam_type']}"
    )

    # ── Step 4: segment questions ──────────────────────────────────────────
    logger.info("Step 4: Segmenting questions...")
    raw_segments = segment_all_pages(normalized_pages)
    logger.info(f"  {len(raw_segments)} question segment(s) found")

    if not raw_segments:
        logger.warning(
            "No questions were detected. "
            "The PDF may use an unusual numbering format."
        )
        return ParsedDocument(
            document_id=document_id,
            year=doc_meta["year"],
            exam_type=doc_meta["exam_type"],
            total_pages=total_pages,
        )

    # ── Step 5: enrich each segment with metadata ─────────────────────────
    logger.info("Step 5: Extracting question-level metadata...")
    enriched = enrich_questions_with_metadata(
        questions=raw_segments,
        document_metadata=doc_meta,
        global_marks=global_marks,
    )

    # ── Step 6: build validated Question objects ───────────────────────────
    logger.info("Step 6: Building Question objects...")
    questions = _build_questions(enriched, document_id)
    logger.info(f"  {len(questions)} validated Question object(s) created")

    # ── Assemble and return the ParsedDocument ─────────────────────────────
    result = ParsedDocument(
        document_id=document_id,
        year=doc_meta["year"],
        exam_type=doc_meta["exam_type"],
        total_pages=total_pages,
        questions=questions,
    )

    logger.info(
        f"━━━ Parse complete: {len(questions)} questions from "
        f"{total_pages} pages ━━━"
    )
    return result


# ═══════════════════════════════════════════════════════════════════
# CONVENIENCE WRAPPERS
# ═══════════════════════════════════════════════════════════════════

def parse_to_json(pdf_path: str, document_id: int) -> dict:
    """
    Parse a question paper and return the result as a plain dict.

    Useful when you need raw dict output (e.g. for the API response).

    Returns
    -------
    dict
        The parsed document as a Python dictionary.
        All None values appear as None (Python) — use json.dumps()
        to convert to JSON string with null values.
    """
    result = parse_question_paper(pdf_path, document_id)
    return result.model_dump()


def parse_to_json_file(
    pdf_path: str,
    document_id: int,
    output_path: str,
) -> str:
    """
    Parse a question paper and save the result to a JSON file.

    Parameters
    ----------
    pdf_path : str
        Path to the input PDF.
    document_id : int
        Document ID from Member 6's ingestion system.
    output_path : str
        Where to save the JSON file.
        E.g. "backend/output/parsed_questions.json"

    Returns
    -------
    str
        The output_path where the file was saved.

    Example
    -------
        path = parse_to_json_file(
            "data/papers/dbms_2025.pdf",
            document_id=101,
            output_path="output/dbms_2025_parsed.json"
        )
        print(f"Saved to {path}")
    """
    result = parse_question_paper(pdf_path, document_id)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    logger.info(f"Output saved to: {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════
# INTERNAL PIPELINE STEPS
# ═══════════════════════════════════════════════════════════════════

def _extract_all_page_text(pdf_path: str) -> list[dict]:
    """
    Step 1: Extract text from every page.
    Uses pdfplumber for text-layer pages, OCR for image-only pages.

    Returns a unified list of page dicts, each with:
        page_number, text, source ("embedded" or "ocr")
    """
    pages_from_reader = extract_pages(pdf_path)
    unified_pages = []

    for page in pages_from_reader:
        page_num = page["page_number"]

        if page["has_text"]:
            # Text layer available — use it directly
            unified_pages.append({
                "page_number": page_num,
                "text":        page["embedded_text"],
                "source":      "embedded",
            })
            logger.debug(f"  Page {page_num}: text layer used")

        else:
            # No text layer — fall back to OCR
            logger.debug(f"  Page {page_num}: no text layer, running OCR...")
            ocr_result = ocr_page(pdf_path, page_num)
            ocr_text = ocr_result.get("ocr_text", "")

            if ocr_text:
                unified_pages.append({
                    "page_number": page_num,
                    "text":        ocr_text,
                    "source":      "ocr",
                })
                logger.debug(f"  Page {page_num}: OCR extracted {len(ocr_text)} chars")
            else:
                # OCR also failed — skip this page
                logger.warning(
                    f"  Page {page_num}: both text extraction and OCR failed. "
                    "Page will be skipped."
                )

    return unified_pages


def _normalize_pages(raw_pages: list[dict]) -> list[dict]:
    """
    Step 2: Apply normalizer.normalize() to each page's text.
    Adds "normalized_text" key to each page dict.
    """
    result = []
    for page in raw_pages:
        page = dict(page)  # copy — don't mutate original
        page["normalized_text"] = normalize(
            page["text"],
            source=page.get("source", "embedded")
        )
        result.append(page)
    return result


def _get_header_text(normalized_pages: list[dict], max_pages: int = 2) -> str:
    """
    Step 3 helper: Combine the first N pages into one string for
    document-level metadata extraction.

    The document header (year, exam_type, university name, etc.)
    almost always appears on the first 1-2 pages.
    """
    header_parts = []
    for page in normalized_pages[:max_pages]:
        text = page.get("normalized_text", "")
        if text:
            header_parts.append(text)
    return "\n".join(header_parts)


def _build_questions(
    enriched_segments: list[dict],
    document_id: int,
) -> list[Question]:
    """
    Step 6: Convert enriched segment dicts into validated Question objects.

    For each segment, calls make_question() which generates a UUID
    and enforces the Pydantic contract.

    Segments that fail validation are skipped with a warning log
    (e.g. if raw_text is somehow empty after processing).
    """
    questions = []

    for i, seg in enumerate(enriched_segments):
        raw_text = seg.get("raw_text", "").strip()

        if not raw_text:
            logger.warning(
                f"Segment {i+1} has empty raw_text after processing — skipped."
            )
            continue

        try:
            q = make_question(
                document_id   = document_id,
                page          = seg.get("page_number", 1),
                raw_text      = raw_text,
                year          = seg.get("year"),
                exam_type     = seg.get("exam_type"),
                section       = seg.get("section"),
                marks         = seg.get("marks"),
                is_compulsory = seg.get("is_compulsory"),
            )
            questions.append(q)

        except Exception as e:
            # Never let one bad segment crash the whole parse
            logger.error(
                f"Could not build Question for segment {i+1}: {e}. "
                f"raw_text preview: '{raw_text[:60]}'"
            )
            continue

    return questions
