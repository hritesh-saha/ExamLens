import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ocr.math_ocr import validate_latex
from app.ocr.models import (
    EquationResult, OCRWord, PageOCRResult, TextBlockResult,
)
from app.ocr.pipeline import run_ocr_and_math
from app.vision.models import CleanedPage, Region

tess = pytest.importorskip("pytesseract")


def _board(path, text="Newton second law", dark=False):
    img = Image.new("L", (900, 220), 20 if dark else 255)
    ImageDraw.Draw(img).text((30, 60), text, fill=235 if dark else 0,
                             font=ImageFont.load_default(size=64))
    img.convert("RGB").save(path)


def _page(path, regions):
    return CleanedPage(document_id=1, page_number=1, source_page_numbers=[1],
                       doc_type="lecture_board", image_path=str(path), regions=regions)


def test_text_region_ocr_has_word_confidence(tmp_path):
    p = tmp_path / "p.png"
    _board(p)
    r = Region(region_id="r1", region_type="text", x=0, y=0, width=900, height=220)
    out = run_ocr_and_math([_page(p, [r])])[0]
    assert "newton" in out.text.lower()
    words = out.text_blocks[0].words
    assert words and all(0 <= w.confidence <= 1 for w in words)
    assert 0 < out.confidence <= 1


def test_dark_board_is_inverted(tmp_path):
    p = tmp_path / "d.png"
    _board(p, dark=True)
    r = Region(region_id="r1", region_type="text", x=0, y=0, width=900, height=220)
    out = run_ocr_and_math([_page(p, [r])])[0]
    assert "newton" in out.text.lower()


def test_no_regions_falls_back_to_full_page(tmp_path):
    p = tmp_path / "f.png"
    _board(p)
    out = run_ocr_and_math([_page(p, [])])[0]
    assert "law" in out.text.lower()


def test_bad_page_does_not_stop_others(tmp_path):
    good = tmp_path / "g.png"
    _board(good)
    bad = _page(tmp_path / "missing.png", [])
    out = run_ocr_and_math([bad, _page(good, [])])
    assert len(out) == 1


def test_validate_latex():
    assert validate_latex(r"\frac{a}{b} + x^{2}")
    assert not validate_latex(r"\frac{a}{b")
    assert not validate_latex("")
    assert validate_latex(r"\begin{matrix} a & b \end{matrix}")


def test_rebuild_flags_and_correction():
    w = lambda i, t, c: OCRWord(word_id=f"r:{i}", text=t, confidence=c, x=i * 10, y=0, w=9, h=9)
    res = PageOCRResult(
        document_id=1, page_number=1,
        text_blocks=[TextBlockResult(region_id="r", x=0, y=5, width=50, height=10,
                                     words=[w(0, "Force", 0.95), w(1, "ecuals", 0.30)])],
        equations=[EquationResult(region_id="e", x=0, y=50, width=10, height=10,
                                  latex="F = m a", confidence=0.9, render_ok=True)],
    )
    res.rebuild()
    assert [x.low_confidence for x in res.text_blocks[0].words] == [False, True]
    assert "$$ F = m a $$" in res.text and res.latex == "F = m a"
    res.text_blocks[0].words[1].text, res.text_blocks[0].words[1].confidence = "equals", 1.0
    res.text_blocks[0].words[1].corrected = True
    res.rebuild()
    assert not res.text_blocks[0].words[1].low_confidence
    assert "Force equals" in res.text
