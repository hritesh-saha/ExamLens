"""
test_vision_dedup.py
====================
Tests for Member 1 page-level duplicate detection.

Images are drawn in memory. No database, API, or OCR is used.
"""

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import SharedPageContract
from app.vision.dedup import deduplicate_pages
from app.vision.models import CleanedPage, Region
from app.vision.pipeline import process_board_images


def _write_png(path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"failed to write {path}")


def _board_image(label: str = "A") -> np.ndarray:
    image = np.full((240, 320, 3), 230, dtype=np.uint8)
    cv2.putText(image, label, (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (20, 20, 20), 3)
    cv2.rectangle(image, (40, 110), (280, 180), (30, 30, 30), 2)
    cv2.line(image, (50, 200), (270, 200), (25, 25, 25), 3)
    return image


def _page(
    tmp_path,
    *,
    document_id: int,
    page_number: int,
    image: np.ndarray,
    name: str | None = None,
    regions: list[Region] | None = None,
) -> CleanedPage:
    filename = name or f"d{document_id}_p{page_number}.png"
    path = tmp_path / filename
    _write_png(path, image)
    return CleanedPage(
        document_id=document_id,
        page_number=page_number,
        source_page_numbers=[page_number],
        doc_type="lecture_board",
        image_path=str(path),
        embedded_text="notes",
        timestamp="2026-09-22",
        regions=regions or [],
    )


def test_empty_list_returns_empty_list():
    assert deduplicate_pages([]) == []


def test_single_page_is_unchanged(tmp_path):
    page = _page(tmp_path, document_id=1, page_number=1, image=_board_image())

    result = deduplicate_pages([page])

    assert len(result) == 1
    assert result[0].page_number == 1
    assert result[0].source_page_numbers == [1]
    assert result[0].image_path == page.image_path


def test_two_identical_images_are_deduplicated(tmp_path):
    image = _board_image("FT")
    first = _page(tmp_path, document_id=1, page_number=1, image=image)
    second = _page(tmp_path, document_id=1, page_number=2, image=image)

    result = deduplicate_pages([first, second])

    assert len(result) == 1
    assert result[0].page_number == 1
    assert result[0].source_page_numbers == [1, 2]


def test_three_identical_images_fold_into_one(tmp_path):
    image = _board_image("FT")
    pages = [
        _page(tmp_path, document_id=4, page_number=n, image=image)
        for n in (1, 2, 3)
    ]

    result = deduplicate_pages(pages)

    assert len(result) == 1
    assert result[0].source_page_numbers == [1, 2, 3]


def test_meaningfully_different_pages_are_kept(tmp_path):
    left = _page(tmp_path, document_id=1, page_number=1, image=_board_image("AAA"))
    right = _page(tmp_path, document_id=1, page_number=2, image=_board_image("ZZZ"))

    result = deduplicate_pages([left, right])

    assert [page.page_number for page in result] == [1, 2]


def test_partial_overlap_is_not_deduplicated(tmp_path):
    shared = np.full((240, 320, 3), 230, dtype=np.uint8)
    cv2.rectangle(shared, (10, 20), (150, 220), (40, 40, 40), thickness=-1)
    only_a = shared.copy()
    cv2.putText(only_a, "AAAA", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
    only_b = shared.copy()
    cv2.rectangle(only_b, (170, 20), (310, 220), (20, 80, 180), thickness=-1)
    cv2.putText(only_b, "BBBB", (180, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (230, 230, 230), 2)

    first = _page(tmp_path, document_id=1, page_number=1, image=only_a)
    second = _page(tmp_path, document_id=1, page_number=2, image=only_b)

    result = deduplicate_pages([first, second])

    assert len(result) == 2


def test_different_documents_are_never_deduplicated(tmp_path):
    image = _board_image("SAME")
    first = _page(tmp_path, document_id=1, page_number=1, image=image)
    second = _page(tmp_path, document_id=2, page_number=1, image=image)

    result = deduplicate_pages([first, second])

    assert len(result) == 2
    assert [page.document_id for page in result] == [1, 2]


def test_input_order_is_preserved(tmp_path):
    images = []
    for index, color in enumerate([(40, 40, 40), (20, 90, 180), (40, 160, 40)]):
        image = np.full((240, 320, 3), 230, dtype=np.uint8)
        cv2.rectangle(image, (20 + index * 80, 30), (90 + index * 80, 210), color, thickness=-1)
        images.append(image)
    pages = [
        _page(tmp_path, document_id=1, page_number=n, image=image)
        for n, image in zip((1, 2, 3), images)
    ]

    result = deduplicate_pages(pages)

    assert [page.page_number for page in result] == [1, 2, 3]


def test_unreadable_image_is_kept(tmp_path):
    readable = _page(tmp_path, document_id=1, page_number=1, image=_board_image())
    broken = CleanedPage(
        document_id=1,
        page_number=2,
        source_page_numbers=[2],
        doc_type="lecture_board",
        image_path=str(tmp_path / "missing.png"),
        timestamp="2026-09-22",
    )

    result = deduplicate_pages([readable, broken])

    assert len(result) == 2
    assert result[1].page_number == 2


def test_retained_page_keeps_metadata_and_regions(tmp_path):
    region = Region(region_id="r001", region_type="text", x=4, y=6, width=40, height=12)
    image = _board_image("FT")
    first = _page(
        tmp_path,
        document_id=9,
        page_number=1,
        image=image,
        regions=[region],
    )
    second = _page(tmp_path, document_id=9, page_number=2, image=image)
    original_bytes = open(first.image_path, "rb").read()
    duplicate_bytes = open(second.image_path, "rb").read()

    result = deduplicate_pages([first, second])

    kept = result[0]
    assert kept.document_id == 9
    assert kept.page_number == 1
    assert kept.timestamp == "2026-09-22"
    assert kept.image_path == first.image_path
    assert kept.regions == [region]
    assert kept.source_page_numbers == [1, 2]
    assert open(first.image_path, "rb").read() == original_bytes
    assert open(second.image_path, "rb").read() == duplicate_bytes
    assert os.path.isfile(first.image_path)
    assert os.path.isfile(second.image_path)


def test_pipeline_deduplicates_two_identical_lecture_pages(tmp_path):
    photo = np.full((600, 800, 3), 25, dtype=np.uint8)
    corners = np.array([[140, 70], [680, 50], [710, 520], [110, 500]], dtype=np.int32)
    cv2.fillPoly(photo, [corners], (235, 235, 235))
    cv2.line(photo, (220, 180), (620, 190), (30, 30, 30), 5)
    cv2.line(photo, (220, 230), (600, 240), (30, 30, 30), 5)
    cv2.line(photo, (220, 280), (580, 290), (30, 30, 30), 5)

    source_a = tmp_path / "pages" / "page_1.png"
    source_b = tmp_path / "pages" / "page_2.png"
    _write_png(source_a, photo)
    _write_png(source_b, photo)
    bytes_a = source_a.read_bytes()
    bytes_b = source_b.read_bytes()

    pages = [
        SharedPageContract(
            document_id=9,
            page_number=1,
            doc_type="lecture_board",
            image_path=str(source_a),
            embedded_text="induction proof",
            timestamp="2026-09-22",
        ),
        SharedPageContract(
            document_id=9,
            page_number=2,
            doc_type="lecture_board",
            image_path=str(source_b),
            embedded_text="induction proof",
            timestamp="2026-09-22",
        ),
    ]

    result = process_board_images(pages)

    assert len(result) == 1
    assert result[0].source_page_numbers == [1, 2]
    assert result[0].document_id == 9
    assert result[0].page_number == 1
    assert result[0].timestamp == "2026-09-22"
    assert result[0].embedded_text == "induction proof"
    assert result[0].regions
    assert source_a.read_bytes() == bytes_a
    assert source_b.read_bytes() == bytes_b
    assert (tmp_path / "pages" / "cleaned" / "page_1.png").is_file()
    assert (tmp_path / "pages" / "cleaned" / "page_2.png").is_file()
