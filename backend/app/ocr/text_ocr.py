"""Text OCR with word-level confidence.

Engines (env OCR_ENGINE = auto | tesseract | easyocr):
  tesseract - native word-level confidence via image_to_data (default fallback)
  easyocr   - better on handwriting / chalk; returns line-level boxes, so the
              line confidence is shared by its words (split by character count)
"""

import os
from functools import lru_cache

import cv2
import numpy as np

from app.ocr.models import OCRWord

MIN_CROP_HEIGHT = 64      # upscale tiny crops so OCR sees enough pixels
PAD = 12


def preprocess(bgr: np.ndarray) -> tuple[np.ndarray, float]:
    """Grayscale, invert dark boards, pad, upscale. Returns (image, scale)."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    if gray.mean() < 110:                     # light ink on dark board
        gray = 255 - gray
    scale = 1.0
    if gray.shape[0] < MIN_CROP_HEIGHT:
        scale = MIN_CROP_HEIGHT / gray.shape[0]
    elif gray.shape[0] < 1000:
        scale = 2.0                           # Tesseract likes ~30px x-height
    if scale != 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.copyMakeBorder(gray, PAD, PAD, PAD, PAD, cv2.BORDER_CONSTANT, value=255)
    return gray, scale


def _engine_name() -> str:
    name = os.getenv("OCR_ENGINE", "auto").lower()
    if name == "auto":
        try:
            import easyocr  # noqa: F401
            return "easyocr"
        except ImportError:
            return "tesseract"
    return name


@lru_cache(maxsize=1)
def _easyocr_reader():
    import easyocr
    return easyocr.Reader(["en"], gpu=False, verbose=False)


def _tesseract_words(img: np.ndarray) -> list[tuple[str, float, int, int, int, int, int]]:
    import pytesseract
    d = pytesseract.image_to_data(
        img, config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT
    )
    out = []
    for i, txt in enumerate(d["text"]):
        txt = txt.strip()
        try:
            conf = float(d["conf"][i])
        except ValueError:
            continue
        if not txt or conf < 0:
            continue
        line = d["block_num"][i] * 1000 + d["par_num"][i] * 100 + d["line_num"][i]
        out.append((txt, conf / 100.0, d["left"][i], d["top"][i], d["width"][i], d["height"][i], line))
    return out


def _easyocr_words(img: np.ndarray) -> list[tuple[str, float, int, int, int, int, int]]:
    out = []
    for li, (box, txt, conf) in enumerate(_easyocr_reader().readtext(img)):
        toks = txt.split()
        if not toks:
            continue
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
        total = sum(len(t) for t in toks) + len(toks) - 1
        cur = x0
        for t in toks:
            wpx = int((x1 - x0) * len(t) / total)
            out.append((t, float(conf), cur, y0, wpx, y1 - y0, li))
            cur += wpx + int((x1 - x0) / total)
    return out


def ocr_text_image(bgr: np.ndarray, region_id: str, ox: int = 0, oy: int = 0) -> list[OCRWord]:
    """OCR one crop. (ox, oy) is the crop's offset on the page, so boxes come
    back in page coordinates."""
    img, scale = preprocess(bgr)
    raw = _easyocr_words(img) if _engine_name() == "easyocr" else _tesseract_words(img)
    words = []
    for idx, (txt, conf, x, y, w, h, line) in enumerate(raw):
        words.append(OCRWord(
            word_id=f"{region_id}:{idx}",
            text=txt,
            confidence=round(max(0.0, min(1.0, conf)), 4),
            x=int((x - PAD) / scale) + ox,
            y=int((y - PAD) / scale) + oy,
            w=max(1, int(w / scale)),
            h=max(1, int(h / scale)),
            line_id=line,
        ))
    return words
