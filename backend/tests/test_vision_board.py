"""
test_vision_board.py
====================
Tests for Member 1 board detection and perspective correction.

Images are drawn in memory. No database, API, or OCR is used.
"""

import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import SharedPageContract
from app.vision.board import detect_board_quadrilateral
from app.vision.pipeline import process_board_images
from app.vision.warp import order_points, perspective_warp


def _quad_board(width: int = 800, height: int = 600) -> tuple[np.ndarray, np.ndarray]:
    """Dark photo with one light, perspective-shaped board inset from the edges."""
    image = np.full((height, width, 3), 25, dtype=np.uint8)
    corners = np.array(
        [[140, 70], [680, 50], [710, 520], [110, 500]],
        dtype=np.int32,
    )
    cv2.fillPoly(image, [corners], (235, 235, 235))
    return image, corners.astype(np.float32)


def _write_png(path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"failed to write {path}")


def test_order_points_puts_corners_in_reading_order():
    top_left = (10, 20)
    top_right = (110, 25)
    bottom_right = (100, 90)
    bottom_left = (15, 80)
    scrambled = np.array(
        [bottom_right, top_left, bottom_left, top_right],
        dtype=np.float32,
    )

    ordered = order_points(scrambled)

    np.testing.assert_allclose(ordered[0], top_left)
    np.testing.assert_allclose(ordered[1], top_right)
    np.testing.assert_allclose(ordered[2], bottom_right)
    np.testing.assert_allclose(ordered[3], bottom_left)


def test_synthetic_quadrilateral_board_is_detected():
    image, expected = _quad_board()

    corners = detect_board_quadrilateral(image)

    assert corners is not None
    assert corners.shape == (4, 2)
    # Each drawn corner should have a detected corner nearby.
    for point in expected:
        distance = np.linalg.norm(corners - point, axis=1).min()
        assert distance < 20


def test_perspective_warp_straightens_a_distorted_board():
    board = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(board, (30, 40), (120, 100), (0, 0, 180), thickness=-1)
    source = np.array(
        [[0, 0], [399, 0], [399, 299], [0, 299]],
        dtype=np.float32,
    )
    distorted_corners = np.array(
        [[90, 40], [520, 30], [540, 390], [70, 410]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(source, distorted_corners)
    photo = cv2.warpPerspective(board, transform, (640, 480))

    restored = perspective_warp(photo, distorted_corners)

    assert restored.ndim == 3 and restored.shape[2] == 3
    assert restored.shape[0] > 1 and restored.shape[1] > 1
    # Size follows the photographed quad's edges, not a fixed canvas.
    top_width = np.linalg.norm(distorted_corners[1] - distorted_corners[0])
    bottom_width = np.linalg.norm(distorted_corners[2] - distorted_corners[3])
    left_height = np.linalg.norm(distorted_corners[3] - distorted_corners[0])
    right_height = np.linalg.norm(distorted_corners[2] - distorted_corners[1])
    assert abs(restored.shape[1] - int(round(max(top_width, bottom_width)))) <= 1
    assert abs(restored.shape[0] - int(round(max(left_height, right_height)))) <= 1
    # The red marker drawn on the board is still present after the warp.
    assert int(restored[:, :, 2].max()) > 150


def test_perspective_warp_has_nonzero_dimensions():
    image, corners = _quad_board()

    warped = perspective_warp(image, corners)

    assert warped.shape[0] > 0
    assert warped.shape[1] > 0
    assert warped.shape[2] == 3


@pytest.mark.parametrize(
    "corners",
    [
        None,
        np.array([[0, 0], [10, 0], [10, 10]], dtype=np.float32),
        np.array([[0, 0], [1, 0], [2, 0], [3, 0]], dtype=np.float32),
        np.array([[0, 0], [10, 0], [10, np.nan], [0, 10]], dtype=np.float32),
    ],
)
def test_invalid_corners_raise_value_error(corners):
    image = np.zeros((40, 40, 3), dtype=np.uint8)

    with pytest.raises(ValueError):
        perspective_warp(image, corners)


def test_blank_image_returns_none_without_crashing():
    blank = np.full((200, 240, 3), 128, dtype=np.uint8)

    assert detect_board_quadrilateral(blank) is None


def test_process_board_images_writes_cleaned_page_and_keeps_original(tmp_path):
    image, _ = _quad_board()
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
    assert len(result) == 1
    assert result[0].document_id == 9
    assert result[0].page_number == 2
    assert result[0].source_page_numbers == [2]
    assert result[0].doc_type == "lecture_board"
    assert result[0].embedded_text == "induction proof"
    assert result[0].timestamp == "2026-09-22"
    assert result[0].regions == []
    assert os.path.realpath(result[0].image_path) == os.path.realpath(cleaned)
    cleaned_image = cv2.imread(str(cleaned))
    assert cleaned_image is not None
    # The straightened board is smaller than the original photo.
    assert cleaned_image.shape[0] < image.shape[0]
    assert cleaned_image.shape[1] < image.shape[1]


def test_pipeline_copies_original_when_no_board_is_found(tmp_path):
    image = np.full((180, 220, 3), 90, dtype=np.uint8)
    source = tmp_path / "uploads" / "pages" / "page_1.png"
    _write_png(source, image)
    original_bytes = source.read_bytes()
    page = SharedPageContract(
        document_id=3,
        page_number=1,
        doc_type="lecture_board",
        image_path=str(source),
        embedded_text=None,
        timestamp="2026-01-01",
    )

    result = process_board_images([page])

    cleaned = source.parent / "cleaned" / "page_1.png"
    assert source.read_bytes() == original_bytes
    assert cleaned.is_file()
    copied = cv2.imread(str(cleaned))
    assert copied.shape == image.shape
    assert result[0].document_id == 3
    assert result[0].timestamp == "2026-01-01"
    assert result[0].embedded_text is None
    assert result[0].page_number == 1
    assert result[0].source_page_numbers == [1]
    assert result[0].regions == []
