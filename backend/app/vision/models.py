"""Output models for the lecture-board vision pipeline.

Coordinates are pixels on the cleaned image. The origin is the top-left corner.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Region(BaseModel):
    """One text, diagram, or equation region on a cleaned page."""

    region_id: str
    region_type: Literal["text", "diagram", "equation"]
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    crop_path: str | None = None


class CleanedPage(BaseModel):
    """One lecture-board page after vision processing.

    page_number is the 1-based index of this cleaned page.
    source_page_numbers lists the ingested pages merged into this image.
    """

    document_id: int = Field(gt=0)
    page_number: int = Field(ge=1)
    source_page_numbers: list[int]
    doc_type: Literal["lecture_board"]
    image_path: str
    embedded_text: str | None = None
    timestamp: str | None = None
    regions: list[Region] = Field(default_factory=list)

    @field_validator("source_page_numbers")
    @classmethod
    def source_pages_must_be_positive(cls, pages: list[int]) -> list[int]:
        for page in pages:
            if page < 1:
                raise ValueError("each source page number must be >= 1")
        return pages
