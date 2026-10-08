"""Page-level duplicate detection for cleaned lecture-board images.

Two pages are duplicates only when the whole board looks like the same
photograph. Partial overlap (a later stitch candidate) is not a duplicate.
Comparison is visual only: no OCR, no text, no language model.
"""

import cv2
import numpy as np

from app.vision.models import CleanedPage

_COMPARE_SIZE = (160, 160)
_FULL_NCC_MIN = 0.93
_QUAD_NCC_MIN = 0.88
# Near-blank pages have almost no structure; do not merge them.
_MIN_STD = 0.02


def deduplicate_pages(pages: list[CleanedPage]) -> list[CleanedPage]:
    """Keep the first copy of each board; fold later copies into it.

    Pages are compared only with earlier retained pages that share the same
    ``document_id``. Order is unchanged. Missing images are kept, never dropped.
    """
    if not pages:
        return []
    if len(pages) == 1:
        return list(pages)

    retained: list[CleanedPage] = []
    fingerprints: list[np.ndarray | None] = []

    for page in pages:
        fingerprint = _fingerprint(page.image_path)
        match_index = _find_duplicate(page, fingerprint, retained, fingerprints)
        if match_index is None:
            retained.append(page)
            fingerprints.append(fingerprint)
            continue
        retained[match_index] = _absorb_duplicate(retained[match_index], page)

    return retained


def _find_duplicate(
    page: CleanedPage,
    fingerprint: np.ndarray | None,
    retained: list[CleanedPage],
    fingerprints: list[np.ndarray | None],
) -> int | None:
    if fingerprint is None:
        return None
    for index, (kept, kept_fp) in enumerate(zip(retained, fingerprints)):
        if kept.document_id != page.document_id:
            continue
        if kept_fp is None:
            continue
        if _is_duplicate(kept_fp, fingerprint):
            return index
    return None


def _absorb_duplicate(kept: CleanedPage, duplicate: CleanedPage) -> CleanedPage:
    """Keep the first page; record the extra source page numbers on it."""
    merged: list[int] = []
    seen: set[int] = set()
    for number in [*kept.source_page_numbers, *duplicate.source_page_numbers]:
        if number not in seen:
            seen.add(number)
            merged.append(number)
    return kept.model_copy(update={"source_page_numbers": merged})


def _fingerprint(image_path: str) -> np.ndarray | None:
    """In-memory comparison image, or None when the file cannot be read."""
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        return None
    resized = cv2.resize(image, _COMPARE_SIZE, interpolation=cv2.INTER_AREA)
    equalized = cv2.equalizeHist(resized)
    # Small blur ignores JPEG/phone noise without hiding a different board.
    blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
    return blurred.astype(np.float32) / 255.0


def _is_duplicate(left: np.ndarray, right: np.ndarray) -> bool:
    """True only when nearly the whole page matches, not just a shared strip."""
    if float(left.std()) < _MIN_STD or float(right.std()) < _MIN_STD:
        return False
    if _ncc(left, right) < _FULL_NCC_MIN:
        return False
    # Partial overlap lights up some tiles and fails others.
    for tile_a, tile_b in zip(_quadrants(left), _quadrants(right)):
        if _ncc(tile_a, tile_b) < _QUAD_NCC_MIN:
            return False
    return True


def _quadrants(image: np.ndarray) -> list[np.ndarray]:
    mid_y, mid_x = image.shape[0] // 2, image.shape[1] // 2
    return [
        image[:mid_y, :mid_x],
        image[:mid_y, mid_x:],
        image[mid_y:, :mid_x],
        image[mid_y:, mid_x:],
    ]


def _ncc(left: np.ndarray, right: np.ndarray) -> float:
    """Normalized correlation of two equal-sized images."""
    a = left.reshape(-1).astype(np.float64)
    b = right.reshape(-1).astype(np.float64)
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom < 1e-8:
        return 0.0
    return float(np.dot(a, b) / denom)
