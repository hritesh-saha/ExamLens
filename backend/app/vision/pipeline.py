"""Member 1 pipeline: board detection, warp, enhancement, regions, dedup, stitch.

Duplicate boards collapse to one CleanedPage. Overlapping photos of the same
board are then stitched. Uncertain pairs stay separate.
"""

from pathlib import Path

import cv2
import numpy as np

from app.schemas import SharedPageContract
from app.vision.board import detect_board_quadrilateral
from app.vision.dedup import deduplicate_pages
from app.vision.enhance import remove_glare_and_shadows
from app.vision.models import CleanedPage
from app.vision.regions import segment_regions
from app.vision.stitch import stitch_pages
from app.vision.warp import perspective_warp


def process_board_images(pages: list[SharedPageContract]) -> list[CleanedPage]:
    """Load each lecture-board page, straighten the board, and save a PNG.

    The cleaned file is written next to the source, under ``pages/cleaned/``.
    The original ``pages/page_N.png`` is never overwritten.

    When no reliable board quadrilateral is found, the original image is kept
    (not a guessed board) and still passed through glare/shadow removal.
    The pipeline does not invent corners and does not stop the remaining pages.
    Near-duplicate pages in the same document are collapsed after segmentation.
    Remaining overlapping photos of the same board are then stitched.
    """
    cleaned_pages = [_process_page(page) for page in pages]
    deduplicated_pages = deduplicate_pages(cleaned_pages)
    return stitch_pages(deduplicated_pages)


def _process_page(page: SharedPageContract) -> CleanedPage:
    if page.doc_type != "lecture_board":
        raise ValueError(
            f"vision pipeline only accepts lecture_board pages, got {page.doc_type!r}"
        )

    image = _load_bgr(page.image_path)
    corners = detect_board_quadrilateral(image)
    if corners is None:
        # Detection failed. Keep the original pixels so a later stage still
        # has an image. This is a copy, not a guessed board outline.
        cleaned = image
    else:
        cleaned = perspective_warp(image, corners)

    cleaned = remove_glare_and_shadows(cleaned)

    output_path = _cleaned_output_path(page.image_path, page.page_number)
    if output_path.resolve() == Path(page.image_path).resolve():
        raise ValueError("refusing to overwrite the original page image")
    if not cv2.imwrite(str(output_path), cleaned):
        raise OSError(f"could not write cleaned image: {output_path}")

    page_id = f"d{page.document_id}_p{page.page_number}"
    regions = segment_regions(
        cleaned,
        page_id=page_id,
        output_dir=output_path.parent,
    )

    return CleanedPage(
        document_id=page.document_id,
        page_number=page.page_number,
        source_page_numbers=[page.page_number],
        doc_type="lecture_board",
        image_path=str(output_path),
        embedded_text=page.embedded_text,
        timestamp=page.timestamp,
        regions=regions,
    )


def _load_bgr(image_path: str) -> np.ndarray:
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"could not read image: {image_path}")
    return image


def _cleaned_output_path(image_path: str, page_number: int) -> Path:
    """``.../pages/page_N.png`` -> ``.../pages/cleaned/page_N.png``."""
    source = Path(image_path)
    cleaned_dir = source.parent / "cleaned"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    return cleaned_dir / f"page_{page_number}.png"
