"""
test_vision.py
==============
Unit tests for Member 1 vision output models.

These tests use only Pydantic. They do not touch OpenCV, the database,
or the network.
"""

import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.vision import CleanedPage, Region


def test_valid_region_can_be_created():
    region = Region(
        region_id="r1",
        region_type="text",
        x=10,
        y=20,
        width=100,
        height=40,
        crop_path=None,
    )

    assert region.region_id == "r1"
    assert region.region_type == "text"
    assert region.x == 10
    assert region.y == 20
    assert region.width == 100
    assert region.height == 40
    assert region.crop_path is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"x": -1},
        {"y": -1},
        {"width": 0},
        {"height": 0},
        {"width": -5},
        {"height": -5},
    ],
)
def test_invalid_region_coordinates_are_rejected(overrides):
    payload = {
        "region_id": "r1",
        "region_type": "diagram",
        "x": 0,
        "y": 0,
        "width": 10,
        "height": 10,
    }
    payload.update(overrides)

    with pytest.raises(ValidationError):
        Region(**payload)


def test_valid_cleaned_page_can_be_created():
    page = CleanedPage(
        document_id=1,
        page_number=1,
        source_page_numbers=[1],
        doc_type="lecture_board",
        image_path="pages/cleaned/page_1.png",
    )

    assert page.document_id == 1
    assert page.page_number == 1
    assert page.source_page_numbers == [1]
    assert page.doc_type == "lecture_board"
    assert page.image_path == "pages/cleaned/page_1.png"
    assert page.embedded_text is None
    assert page.timestamp is None
    assert page.regions == []


def test_cleaned_page_accepts_multiple_source_page_numbers():
    page = CleanedPage(
        document_id=4,
        page_number=1,
        source_page_numbers=[1, 2, 3],
        doc_type="lecture_board",
        image_path="pages/cleaned/page_1.png",
    )

    assert page.source_page_numbers == [1, 2, 3]


def test_cleaned_page_accepts_multiple_regions():
    regions = [
        Region(region_id="t1", region_type="text", x=0, y=0, width=80, height=20),
        Region(
            region_id="d1",
            region_type="diagram",
            x=0,
            y=30,
            width=200,
            height=150,
            crop_path="pages/crops/d1.png",
        ),
        Region(
            region_id="e1",
            region_type="equation",
            x=10,
            y=200,
            width=120,
            height=40,
            crop_path="pages/crops/e1.png",
        ),
    ]
    page = CleanedPage(
        document_id=4,
        page_number=2,
        source_page_numbers=[2],
        doc_type="lecture_board",
        image_path="pages/cleaned/page_2.png",
        regions=regions,
    )

    assert len(page.regions) == 3
    assert [region.region_type for region in page.regions] == [
        "text",
        "diagram",
        "equation",
    ]


def test_lecture_board_doc_type_is_accepted():
    page = CleanedPage(
        document_id=2,
        page_number=1,
        source_page_numbers=[1],
        doc_type="lecture_board",
        image_path="pages/cleaned/page_1.png",
    )

    assert page.doc_type == "lecture_board"


def test_invalid_doc_type_is_rejected():
    with pytest.raises(ValidationError):
        CleanedPage(
            document_id=2,
            page_number=1,
            source_page_numbers=[1],
            doc_type="question_paper",
            image_path="pages/cleaned/page_1.png",
        )
