"""Output models for Member 2 (OCR + Math).

Coordinates are pixels on the cleaned page image (top-left origin), the same
space as Member 1's `Region`. Confidence is always 0-1.
"""

from typing import Optional

from pydantic import BaseModel, Field

LOW_CONF_THRESHOLD = 0.60  # words below this are highlighted in the edit UI


class OCRWord(BaseModel):
    word_id: str                      # "<region_id>:<index>", stable key for corrections
    text: str
    confidence: float = Field(ge=0, le=1)
    x: int
    y: int
    w: int
    h: int
    line_id: int = 0
    low_confidence: bool = False
    corrected: bool = False


class TextBlockResult(BaseModel):
    region_id: str
    x: int
    y: int
    width: int
    height: int
    words: list[OCRWord] = Field(default_factory=list)
    text: str = ""
    mean_confidence: float = 0.0

    def rebuild(self) -> None:
        lines: dict[int, list[OCRWord]] = {}
        for w in self.words:
            lines.setdefault(w.line_id, []).append(w)
        ordered = sorted(lines.values(), key=lambda ws: min(w.y for w in ws))
        self.text = "\n".join(
            " ".join(w.text for w in sorted(ws, key=lambda w: w.x)) for ws in ordered
        )
        self.mean_confidence = (
            sum(w.confidence for w in self.words) / len(self.words) if self.words else 0.0
        )


class EquationResult(BaseModel):
    region_id: str
    x: int
    y: int
    width: int
    height: int
    latex: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    render_ok: bool = False
    low_confidence: bool = True
    corrected: bool = False
    crop_path: Optional[str] = None
    preview_path: Optional[str] = None   # PNG rendered from the LaTeX (for the report/UI)


class PageOCRResult(BaseModel):
    document_id: int
    page_number: int
    source_page_numbers: list[int] = Field(default_factory=list)
    timestamp: Optional[str] = None
    text_blocks: list[TextBlockResult] = Field(default_factory=list)
    equations: list[EquationResult] = Field(default_factory=list)
    text: str = ""          # reading-order text, equations inline as $$...$$
    latex: str = ""         # all equations, one per line
    confidence: float = 0.0
    low_conf_threshold: float = LOW_CONF_THRESHOLD

    def rebuild(self) -> None:
        """Recompute derived fields. Call after any edit/correction."""
        thr = self.low_conf_threshold
        for b in self.text_blocks:
            for w in b.words:
                w.low_confidence = (not w.corrected) and w.confidence < thr
            b.rebuild()
        for e in self.equations:
            e.low_confidence = (not e.corrected) and (e.confidence < thr or not e.render_ok)

        items = [(b.y, b.x, b.text) for b in self.text_blocks if b.text]
        items += [(e.y, e.x, f"$$ {e.latex} $$") for e in self.equations if e.latex]
        self.text = "\n\n".join(t for _, _, t in sorted(items, key=lambda i: (i[0], i[1])))
        self.latex = "\n".join(e.latex for e in self.equations if e.latex)

        words = [w for b in self.text_blocks for w in b.words]
        word_mean = sum(w.confidence for w in words) / len(words) if words else None
        eqs = [e.confidence for e in self.equations if e.latex]
        eq_mean = sum(eqs) / len(eqs) if eqs else None
        parts = [m for m in (word_mean, eq_mean) if m is not None]
        self.confidence = round(sum(parts) / len(parts), 4) if parts else 0.0


class WordCorrection(BaseModel):
    word_id: str
    text: str


class EquationCorrection(BaseModel):
    region_id: str
    latex: str


class CorrectionRequest(BaseModel):
    words: list[WordCorrection] = Field(default_factory=list)
    equations: list[EquationCorrection] = Field(default_factory=list)
