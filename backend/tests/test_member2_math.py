import numpy as np

from app.ocr import math_ocr
from app.ocr.math_ocr import recognize_equation, render_latex_png


class FakeModel:
    """Stands in for pix2tex LatexOCR (not installable in CI)."""
    def __init__(self, outputs):
        self.outputs = list(outputs)

    def __call__(self, img):
        return self.outputs.pop(0)


def _patch(monkeypatch, outputs):
    monkeypatch.setattr(math_ocr, "pix2tex_available", lambda: True)
    monkeypatch.setattr(math_ocr, "_model", lambda: FakeModel(outputs))


IMG = np.full((60, 200, 3), 255, np.uint8)


def test_valid_latex_stable_prediction(monkeypatch, tmp_path):
    _patch(monkeypatch, [r"\frac{a}{b}", r"\frac{a}{b}"])
    out = recognize_equation(IMG, str(tmp_path / "e.png"))
    assert out["render_ok"] and out["confidence"] == 1.0
    assert (tmp_path / "e.png").exists()


def test_invalid_latex_is_capped(monkeypatch):
    _patch(monkeypatch, [r"\frac{a", r"\frac{a"])
    out = recognize_equation(IMG)
    assert not out["render_ok"] and out["confidence"] <= 0.30


def test_unstable_prediction_lowers_confidence(monkeypatch):
    _patch(monkeypatch, [r"x^{2}+y", r"\sum_{i=1}^{n} z_i"])
    assert recognize_equation(IMG)["confidence"] < 0.6


def test_missing_model_never_raises(monkeypatch):
    monkeypatch.setattr(math_ocr, "pix2tex_available", lambda: False)
    assert recognize_equation(IMG)["latex"] == ""


def test_render_png(tmp_path):
    assert render_latex_png(r"E = m c^{2}", str(tmp_path / "x.png"))
