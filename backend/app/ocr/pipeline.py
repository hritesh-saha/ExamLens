"""Member 2 entry point.

    run_ocr_and_math(cleaned_pages) -> list[PageOCRResult]

`cleaned_pages` are Member 1's CleanedPage objects. Text regions are cropped
from the cleaned image by coordinates; equation regions use their crop_path.
Diagram regions are skipped (Member 1 already saved them as images).
"""

from pathlib import Path

import cv2

from app.ocr.math_ocr import recognize_equation
from app.ocr.models import (
    LOW_CONF_THRESHOLD, EquationResult, PageOCRResult, TextBlockResult,
)
from app.ocr.text_ocr import ocr_text_image

OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output" / "ocr"


def _crop(img, r, margin: int = 4):
    h, w = img.shape[:2]
    x0, y0 = max(0, r.x - margin), max(0, r.y - margin)
    return img[y0:min(h, r.y + r.height + margin), x0:min(w, r.x + r.width + margin)], x0, y0


def process_page(page, threshold: float = LOW_CONF_THRESHOLD) -> PageOCRResult:
    img = cv2.imread(page.image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"cannot read {page.image_path}")

    res = PageOCRResult(
        document_id=page.document_id,
        page_number=page.page_number,
        source_page_numbers=list(page.source_page_numbers),
        timestamp=page.timestamp,
        low_conf_threshold=threshold,
    )
    prev_dir = OUTPUT_ROOT / f"doc_{page.document_id}" / "equations"

    regions = list(page.regions)
    if not any(r.region_type in ("text", "equation") for r in regions):
        # Vision found nothing usable: OCR the whole page as one block.
        h, w = img.shape[:2]
        words = ocr_text_image(img, f"d{page.document_id}_p{page.page_number}_full")
        blk = TextBlockResult(region_id="full", x=0, y=0, width=w, height=h, words=words)
        res.text_blocks.append(blk)

    for r in regions:
        if r.region_type == "text":
            crop, ox, oy = _crop(img, r)
            if crop.size == 0:
                continue
            res.text_blocks.append(TextBlockResult(
                region_id=r.region_id, x=r.x, y=r.y, width=r.width, height=r.height,
                words=ocr_text_image(crop, r.region_id, ox, oy),
            ))
        elif r.region_type == "equation":
            crop = cv2.imread(r.crop_path) if r.crop_path else None
            if crop is None:
                crop, _, _ = _crop(img, r)
            out = recognize_equation(crop, str(prev_dir / f"{r.region_id}.png"))
            res.equations.append(EquationResult(
                region_id=r.region_id, x=r.x, y=r.y, width=r.width, height=r.height,
                crop_path=r.crop_path, **out,
            ))
    res.rebuild()
    return res


def run_ocr_and_math(cleaned_pages, threshold: float = LOW_CONF_THRESHOLD) -> list[PageOCRResult]:
    """One bad page never stops the rest (same rule as Member 1)."""
    results = []
    for p in cleaned_pages:
        try:
            results.append(process_page(p, threshold))
        except Exception as e:   # noqa: BLE001
            print(f"[ocr] page {p.page_number} failed: {e}")
    return results
