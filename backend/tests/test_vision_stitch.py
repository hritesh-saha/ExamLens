"""
test_vision_stitch.py
=====================
Tests for Member 1 multi-photo board stitching.

Images are drawn in memory. No database, API, or OCR is used.
"""

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.vision.models import CleanedPage, Region
from app.vision.stitch import stitch_pages


def _write_png(path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"failed to write {path}")


def _feature_board(width: int = 900, height: int = 280) -> np.ndarray:
    """A board with unique markers in both directions so ORB can lock overlap."""
    image = np.full((height, width, 3), 235, dtype=np.uint8)
    cv2.rectangle(image, (6, 6), (width - 7, height - 7), (35, 35, 35), 3)
    index = 0
    y = 16
    while y < height - 42:
        x = 16
        while x < width - 42:
            for bit in range(9):
                row, col = divmod(bit, 3)
                if ((index + 1) * (bit + 3) + index * 5) % 2 == 1:
                    px = x + col * 8
                    py = y + row * 8
                    cv2.rectangle(
                        image, (px, py), (px + 6, py + 6), (18, 18, 18), thickness=-1
                    )
            if index % 3 == 0:
                cv2.circle(image, (x + 20, y + 26), 4 + index % 5, (12, 12, 12), 2)
            x += 30 + (index * 3) % 11
            index += 1
        y += 38 + (index % 7)
    return image


def _page(
    tmp_path,
    *,
    document_id: int,
    page_number: int,
    image: np.ndarray,
    name: str | None = None,
) -> CleanedPage:
    filename = name or f"d{document_id}_p{page_number}.png"
    path = tmp_path / "pages" / "cleaned" / filename
    _write_png(path, image)
    return CleanedPage(
        document_id=document_id,
        page_number=page_number,
        source_page_numbers=[page_number],
        doc_type="lecture_board",
        image_path=str(path),
        embedded_text="notes",
        timestamp="2026-09-22",
        regions=[
            Region(region_id="r001", region_type="text", x=4, y=4, width=20, height=10)
        ],
    )


def test_empty_input_returns_empty_list():
    assert stitch_pages([]) == []


def test_single_page_is_unchanged(tmp_path):
    page = _page(tmp_path, document_id=1, page_number=1, image=_feature_board())

    result = stitch_pages([page])

    assert len(result) == 1
    assert result[0].image_path == page.image_path
    assert result[0].source_page_numbers == [1]


def test_unreadable_image_stays_separate(tmp_path):
    readable = _page(tmp_path, document_id=1, page_number=1, image=_feature_board())
    broken = CleanedPage(
        document_id=1,
        page_number=2,
        source_page_numbers=[2],
        doc_type="lecture_board",
        image_path=str(tmp_path / "missing.png"),
        timestamp="2026-09-22",
    )

    result = stitch_pages([readable, broken])

    assert len(result) == 2
    assert result[1].page_number == 2


def test_smooth_image_with_no_descriptors_stays_separate(tmp_path):
    blank_a = np.full((180, 240, 3), 180, dtype=np.uint8)
    blank_b = np.full((180, 240, 3), 190, dtype=np.uint8)
    first = _page(tmp_path, document_id=1, page_number=1, image=blank_a)
    second = _page(tmp_path, document_id=1, page_number=2, image=blank_b)

    result = stitch_pages([first, second])

    assert len(result) == 2


def test_unrelated_images_remain_separate(tmp_path):
    left = np.full((220, 300, 3), 240, dtype=np.uint8)
    right = np.full((220, 300, 3), 240, dtype=np.uint8)
    cv2.rectangle(left, (20, 20), (120, 160), (10, 10, 200), thickness=-1)
    cv2.circle(left, (80, 80), 30, (0, 0, 0), 3)
    cv2.rectangle(right, (160, 40), (270, 200), (10, 180, 30), thickness=-1)
    cv2.line(right, (20, 200), (280, 30), (0, 0, 0), 4)
    first = _page(tmp_path, document_id=1, page_number=1, image=left)
    second = _page(tmp_path, document_id=1, page_number=2, image=right)

    result = stitch_pages([first, second])

    assert len(result) == 2


def test_different_documents_never_stitch(tmp_path):
    board = _feature_board()
    first = _page(tmp_path, document_id=1, page_number=1, image=board[:, :500])
    second = _page(tmp_path, document_id=2, page_number=1, image=board[:, 400:])

    result = stitch_pages([first, second])

    assert len(result) == 2
    assert [page.document_id for page in result] == [1, 2]


def test_horizontal_overlap_is_stitched(tmp_path):
    board = _feature_board(900, 280)
    left = _page(tmp_path, document_id=3, page_number=1, image=board[:, :560])
    right = _page(tmp_path, document_id=3, page_number=2, image=board[:, 340:])
    left_bytes = open(left.image_path, "rb").read()
    right_bytes = open(right.image_path, "rb").read()

    result = stitch_pages([left, right])

    assert len(result) == 1
    kept = result[0]
    assert kept.document_id == 3
    assert kept.page_number == 1
    assert kept.source_page_numbers == [1, 2]
    assert kept.timestamp == "2026-09-22"
    assert kept.doc_type == "lecture_board"
    assert kept.regions == []
    assert os.path.isfile(kept.image_path)
    panorama = cv2.imread(kept.image_path)
    assert panorama is not None
    assert panorama.shape[1] > 560
    assert panorama.shape[1] < 900 * 2
    assert panorama.shape[0] < 280 * 2
    assert open(left.image_path, "rb").read() == left_bytes
    assert open(right.image_path, "rb").read() == right_bytes
    assert "stitched" in kept.image_path.replace("\\", "/")


def test_vertical_overlap_is_stitched(tmp_path):
    board = _feature_board(320, 700)
    top = _page(tmp_path, document_id=4, page_number=1, image=board[:440, :])
    bottom = _page(tmp_path, document_id=4, page_number=2, image=board[260:, :])

    result = stitch_pages([top, bottom])

    assert len(result) == 1
    panorama = cv2.imread(result[0].image_path)
    assert panorama is not None
    assert panorama.shape[0] > 440
    assert result[0].source_page_numbers == [1, 2]


def test_three_sequential_overlapping_pages(tmp_path):
    board = _feature_board(1000, 260)
    first = _page(tmp_path, document_id=5, page_number=1, image=board[:, :520])
    second = _page(tmp_path, document_id=5, page_number=2, image=board[:, 250:760])
    third = _page(tmp_path, document_id=5, page_number=3, image=board[:, 490:])

    result = stitch_pages([first, second, third])

    assert len(result) == 1
    assert result[0].source_page_numbers == [1, 2, 3]
    assert result[0].page_number == 1
    panorama = cv2.imread(result[0].image_path)
    assert panorama is not None
    assert panorama.shape[1] > 460


def test_failed_stitch_does_not_crash_and_keeps_later_page(tmp_path):
    board = _feature_board()
    first = _page(tmp_path, document_id=6, page_number=1, image=board[:, :500])
    noise = np.full((200, 220, 3), 128, dtype=np.uint8)
    second = _page(tmp_path, document_id=6, page_number=2, image=noise)
    third = _page(tmp_path, document_id=6, page_number=3, image=board[:, 400:])

    result = stitch_pages([first, second, third])

    assert len(result) >= 2
    assert result[0].page_number == 1
    assert any(page.page_number == 2 for page in result)


def test_input_order_is_preserved_for_separate_pages(tmp_path):
    a = np.full((160, 200, 3), 240, dtype=np.uint8)
    b = np.full((160, 200, 3), 240, dtype=np.uint8)
    c = np.full((160, 200, 3), 240, dtype=np.uint8)
    cv2.rectangle(a, (10, 10), (80, 140), (200, 20, 20), thickness=-1)
    cv2.circle(b, (100, 80), 40, (20, 200, 20), thickness=-1)
    cv2.line(c, (10, 10), (190, 150), (20, 20, 200), 6)
    pages = [
        _page(tmp_path, document_id=7, page_number=1, image=a),
        _page(tmp_path, document_id=7, page_number=2, image=b),
        _page(tmp_path, document_id=7, page_number=3, image=c),
    ]

    result = stitch_pages(pages)

    assert [page.page_number for page in result] == [1, 2, 3]
