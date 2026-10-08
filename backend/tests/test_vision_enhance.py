"""
test_vision_enhance.py
======================
Tests for Member 1 glare/shadow removal.

Images are drawn in memory. No database, API, or OCR is used.
"""

import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import SharedPageContract
from app.vision.enhance import remove_glare_and_shadows
from app.vision.pipeline import process_board_images


def _plain_board(width: int = 320, height: int = 240) -> np.ndarray:
    return np.full((height, width, 3), 210, dtype=np.uint8)


def _gradient_board(width: int = 320, height: int = 240) -> np.ndarray:
    """Light board with a dark shadow on the left."""
    ramp = np.linspace(50, 220, width, dtype=np.uint8)
    gray = np.tile(ramp, (height, 1))
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _board_with_writing() -> np.ndarray:
    """Light board with thin dark strokes, like marker lines."""
    image = _plain_board(400, 300)
    cv2.line(image, (40, 80), (360, 80), (20, 20, 20), 3)
    cv2.line(image, (40, 140), (360, 140), (20, 20, 20), 3)
    cv2.line(image, (80, 40), (80, 260), (20, 20, 20), 3)
    return image


def _write_png(path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"failed to write {path}")


def test_normal_bgr_image_is_accepted():
    image = _plain_board()

    result = remove_glare_and_shadows(image)

    assert result is not None
    assert result.dtype == np.uint8


def test_empty_image_raises_value_error():
    with pytest.raises(ValueError):
        remove_glare_and_shadows(np.zeros((0, 0, 3), dtype=np.uint8))


def test_none_raises_value_error():
    with pytest.raises(ValueError):
        remove_glare_and_shadows(None)


def test_unsupported_channel_count_raises_value_error():
    gray = np.full((40, 40), 128, dtype=np.uint8)
    rgba = np.full((40, 40, 4), 128, dtype=np.uint8)

    with pytest.raises(ValueError):
        remove_glare_and_shadows(gray)
    with pytest.raises(ValueError):
        remove_glare_and_shadows(rgba)


def test_output_is_bgr_with_three_channels():
    result = remove_glare_and_shadows(_plain_board())

    assert result.ndim == 3
    assert result.shape[2] == 3


def test_output_dimensions_match_input():
    image = _plain_board(257, 193)

    result = remove_glare_and_shadows(image)

    assert result.shape == image.shape


def test_broad_shadow_gradient_does_not_crash():
    result = remove_glare_and_shadows(_gradient_board())

    assert result.shape == (240, 320, 3)


def test_local_bright_region_does_not_crash():
    image = _plain_board()
    cv2.circle(image, (160, 120), 18, (255, 255, 255), thickness=-1)

    result = remove_glare_and_shadows(image)

    assert result.shape == image.shape


def test_uneven_illumination_is_changed():
    image = _gradient_board()

    result = remove_glare_and_shadows(image)

    assert not np.array_equal(result, image)


def test_fine_writing_is_not_erased():
    image = _board_with_writing()

    result = remove_glare_and_shadows(image)

    # Sample the middle of the horizontal stroke vs nearby board.
    stroke = result[80, 200]
    nearby = result[100, 200]
    assert int(stroke.mean()) < int(nearby.mean()) - 20
    vertical = result[150, 80]
    beside = result[150, 110]
    assert int(vertical.mean()) < int(beside.mean()) - 20


def test_pipeline_still_writes_cleaned_page_without_overwriting(tmp_path):
    image = np.full((600, 800, 3), 25, dtype=np.uint8)
    corners = np.array([[140, 70], [680, 50], [710, 520], [110, 500]], dtype=np.int32)
    cv2.fillPoly(image, [corners], (235, 235, 235))
    cv2.line(image, (200, 200), (600, 220), (30, 30, 30), 4)

    source = tmp_path / "pages" / "page_2.png"
    _write_png(source, image)
    original_bytes = source.read_bytes()
    page = SharedPageContract(
        document_id=9,
        page_number=2,
        doc_type="lecture_board",
        image_path=str(source),
        embedded_text="induction proof",
        timestamp="2026-09-22",
    )

    result = process_board_images([page])

    cleaned = tmp_path / "pages" / "cleaned" / "page_2.png"
    assert source.read_bytes() == original_bytes
    assert cleaned.is_file()
    assert result[0].document_id == 9
    assert result[0].page_number == 2
    assert result[0].source_page_numbers == [2]
    assert result[0].embedded_text == "induction proof"
    assert result[0].timestamp == "2026-09-22"
    assert result[0].regions == []
    assert os.path.realpath(result[0].image_path) == os.path.realpath(cleaned)
    cleaned_image = cv2.imread(str(cleaned))
    assert cleaned_image is not None
    assert cleaned_image.shape[0] < image.shape[0]
    assert cleaned_image.shape[1] < image.shape[1]
    assert cleaned_image.shape[2] == 3
