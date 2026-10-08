"""
test_vision_regions.py
======================
Tests for Member 1 visual region segmentation.

Images are drawn in memory. No database, API, or OCR is used.
"""

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import SharedPageContract
from app.vision.pipeline import process_board_images
from app.vision.regions import segment_regions


def _blank(width: int = 240, height: int = 180) -> np.ndarray:
    return np.full((height, width, 3), 230, dtype=np.uint8)


def _write_png(path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"failed to write {path}")


def test_blank_image_returns_no_regions():
    assert segment_regions(_blank(), page_id="blank") == []


def test_text_like_strokes_produce_a_region():
    image = _blank(400, 280)
    for y in (70, 100, 130):
        cv2.line(image, (40, y), (340, y), (25, 25, 25), 4)

    regions = segment_regions(image, page_id="text")

    assert len(regions) >= 1
    assert all(region.region_type in {"text", "diagram", "equation"} for region in regions)


def test_nearby_character_boxes_are_merged():
    image = _blank(420, 220)
    x = 40
    for _ in range(8):
        cv2.rectangle(image, (x, 90), (x + 14, 122), (20, 20, 20), thickness=-1)
        x += 18

    regions = segment_regions(image, page_id="chars")

    assert 1 <= len(regions) <= 3
    assert len(regions) < 8


def test_region_geometry_is_valid():
    image = _blank(360, 240)
    cv2.line(image, (30, 80), (300, 80), (20, 20, 20), 5)
    cv2.line(image, (30, 110), (300, 110), (20, 20, 20), 5)
    height, width = image.shape[:2]

    regions = segment_regions(image, page_id="geom")

    assert regions
    ids = [region.region_id for region in regions]
    assert len(ids) == len(set(ids))
    for region in regions:
        assert region.width > 0 and region.height > 0
        assert 0 <= region.x < width
        assert 0 <= region.y < height
        assert region.x + region.width <= width
        assert region.y + region.height <= height


def test_regions_are_in_reading_order():
    image = _blank(360, 300)
    cv2.rectangle(image, (40, 40), (120, 80), (20, 20, 20), thickness=-1)
    cv2.rectangle(image, (200, 45), (280, 85), (20, 20, 20), thickness=-1)
    cv2.rectangle(image, (40, 200), (140, 250), (20, 20, 20), thickness=-1)

    regions = segment_regions(image, page_id="order")
    again = segment_regions(image, page_id="order")

    assert len(regions) >= 2
    ys = [region.y + region.height // 2 for region in regions]
    assert ys == sorted(ys)
    assert [region.region_id for region in regions] == [
        region.region_id for region in again
    ]


def test_large_box_structure_is_a_diagram(tmp_path):
    image = _blank(420, 320)
    cv2.rectangle(image, (50, 40), (300, 230), (20, 20, 20), 3)
    cv2.line(image, (70, 200), (270, 70), (20, 20, 20), 3)
    cv2.rectangle(image, (90, 90), (160, 150), (20, 20, 20), 2)

    regions = segment_regions(image, page_id="fig", output_dir=tmp_path)
    diagrams = [region for region in regions if region.region_type == "diagram"]

    assert diagrams
    diagram = diagrams[0]
    assert diagram.crop_path is not None
    assert os.path.isfile(diagram.crop_path)
    assert diagram.crop_path.lower().endswith(".png")
    crop = cv2.imread(diagram.crop_path)
    assert crop is not None
    assert crop.shape[1] == diagram.width
    assert crop.shape[0] == diagram.height


def test_fraction_like_layout_can_be_equation():
    image = _blank(320, 240)
    cv2.rectangle(image, (120, 70), (135, 85), (20, 20, 20), thickness=-1)
    cv2.rectangle(image, (145, 68), (160, 84), (20, 20, 20), thickness=-1)
    cv2.rectangle(image, (170, 72), (182, 86), (20, 20, 20), thickness=-1)
    cv2.line(image, (110, 100), (200, 100), (20, 20, 20), 2)
    cv2.rectangle(image, (125, 115), (140, 130), (20, 20, 20), thickness=-1)
    cv2.rectangle(image, (150, 115), (165, 132), (20, 20, 20), thickness=-1)
    cv2.rectangle(image, (172, 118), (185, 130), (20, 20, 20), thickness=-1)

    regions = segment_regions(image, page_id="eq")
    types = {region.region_type for region in regions}

    assert "equation" in types


def test_simple_strokes_fall_back_to_text():
    image = _blank(400, 260)
    cv2.line(image, (50, 80), (330, 80), (25, 25, 25), 4)
    cv2.line(image, (50, 115), (310, 115), (25, 25, 25), 4)

    regions = segment_regions(image, page_id="plain")

    assert regions
    assert all(region.region_type == "text" for region in regions)
    assert all(region.crop_path is None for region in regions)


def test_pipeline_attaches_regions_without_touching_source(tmp_path):
    image = np.full((600, 800, 3), 25, dtype=np.uint8)
    corners = np.array([[140, 70], [680, 50], [710, 520], [110, 500]], dtype=np.int32)
    cv2.fillPoly(image, [corners], (235, 235, 235))
    cv2.line(image, (220, 180), (620, 190), (30, 30, 30), 5)
    cv2.line(image, (220, 230), (600, 240), (30, 30, 30), 5)
    cv2.line(image, (220, 280), (580, 290), (30, 30, 30), 5)

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
    cleaned_image = cv2.imread(str(cleaned))
    assert source.read_bytes() == original_bytes
    assert cleaned_image is not None
    assert result[0].document_id == 9
    assert result[0].page_number == 2
    assert result[0].source_page_numbers == [2]
    assert result[0].timestamp == "2026-09-22"
    assert result[0].embedded_text == "induction proof"
    assert result[0].regions
    height, width = cleaned_image.shape[:2]
    for region in result[0].regions:
        assert 0 <= region.x < width
        assert 0 <= region.y < height
        assert region.x + region.width <= width
        assert region.y + region.height <= height
