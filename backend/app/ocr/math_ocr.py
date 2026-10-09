"""Equation -> LaTeX (pix2tex) with render validation and a confidence score.

pix2tex does not expose a probability, so confidence is a documented proxy:
  agreement = difflib similarity between LaTeX from the original crop and from
              a 1.25x rescaled crop (stable predictions agree with themselves)
  confidence = agreement if the LaTeX renders, else min(agreement, 0.30)
"""

import os
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image


@lru_cache(maxsize=1)
def _model():
    from pix2tex.cli import LatexOCR   # heavy import (torch), so lazy
    return LatexOCR()


def pix2tex_available() -> bool:
    try:
        import pix2tex  # noqa: F401
        return True
    except ImportError:
        return False


def _balanced(s: str) -> bool:
    depth = 0
    for ch in re.sub(r"\\[{}]", "", s):
        depth += (ch == "{") - (ch == "}")
        if depth < 0:
            return False
    return depth == 0


def validate_latex(latex: str) -> bool:
    """True if the LaTeX parses/renders. Uses matplotlib mathtext; for
    environments mathtext cannot parse (matrix, cases, align) it falls back to
    structural checks (balanced braces, matched \\begin/\\end)."""
    latex = latex.strip()
    if not latex or not _balanced(latex):
        return False
    if re.search(r"\\begin\{", latex):
        return len(re.findall(r"\\begin\{", latex)) == len(re.findall(r"\\end\{", latex))
    try:
        from matplotlib.mathtext import MathTextParser
        MathTextParser("path").parse(f"${latex}$")
        return True
    except Exception:
        return False


def render_latex_png(latex: str, out_path: str) -> str | None:
    """Render LaTeX to a PNG (proof for the report + UI preview)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, f"${latex}$", fontsize=18)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.1, transparent=False)
        plt.close(fig)
        return out_path
    except Exception:
        return None


def _to_pil(bgr: np.ndarray) -> Image.Image:
    rgb = bgr[:, :, ::-1] if bgr.ndim == 3 else np.stack([bgr] * 3, -1)
    return Image.fromarray(np.ascontiguousarray(rgb))


def recognize_equation(bgr: np.ndarray, preview_path: str | None = None) -> dict:
    """Returns {latex, confidence, render_ok, preview_path}. Never raises: a
    missing model or a failed crop yields empty latex + confidence 0."""
    empty = {"latex": "", "confidence": 0.0, "render_ok": False, "preview_path": None}
    if not pix2tex_available():
        return empty
    try:
        img = _to_pil(bgr)
        model = _model()
        a = model(img).strip()
        if not a:
            return empty
        if os.getenv("MATH_CONSISTENCY", "1") == "1":
            big = img.resize((int(img.width * 1.25), int(img.height * 1.25)), Image.LANCZOS)
            b = model(big).strip()
            agreement = SequenceMatcher(None, a, b).ratio()
        else:
            agreement = 0.8
        ok = validate_latex(a)
        conf = agreement if ok else min(agreement, 0.30)
        prev = render_latex_png(a, preview_path) if (ok and preview_path) else None
        return {"latex": a, "confidence": round(conf, 4), "render_ok": ok, "preview_path": prev}
    except Exception:
        return empty
