"""Member 2 evaluation: OCR word accuracy, CER, confidence calibration, LaTeX quality.

Usage (from backend/):
    python -m scripts.eval_ocr --labels data/ocr_eval/labels.json --out output/ocr_eval.json

labels.json (hand-labeled, 30+ text regions and 15+ equations recommended):
[
  {"type": "text",     "image": "data/ocr_eval/t01.png", "text": "ground truth words here"},
  {"type": "equation", "image": "data/ocr_eval/e01.png", "latex": "E = m c ^ { 2 }"}
]
"""

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import cv2

from app.ocr.math_ocr import recognize_equation, validate_latex
from app.ocr.models import LOW_CONF_THRESHOLD
from app.ocr.text_ocr import ocr_text_image


def lev(a, b) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def norm_words(s: str) -> list[str]:
    return re.sub(r"\s+", " ", s.strip().lower()).split(" ")


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def eval_text(items, thr):
    ref_n = err = cer_err = cer_n = 0
    correct_conf, wrong_conf = [], []
    wrong_flagged = wrong_total = 0
    for it in items:
        img = cv2.imread(it["image"])
        words = ocr_text_image(img, "eval")
        hyp = [w.text.lower() for w in words]
        ref = norm_words(it["text"])
        ref_n += len(ref)
        err += lev(ref, hyp)
        r, h = " ".join(ref), " ".join(hyp)
        cer_err += lev(r, h)
        cer_n += len(r)
        # per-word correctness via alignment, for calibration
        eq_idx = set()
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, ref, hyp).get_opcodes():
            if tag == "equal":
                eq_idx.update(range(j1, j2))
        for j, w in enumerate(words):
            if j in eq_idx:
                correct_conf.append(w.confidence)
            else:
                wrong_conf.append(w.confidence)
                wrong_total += 1
                wrong_flagged += w.confidence < thr
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    return {
        "samples": len(items), "reference_words": ref_n,
        "word_error_rate": round(err / max(ref_n, 1), 4),
        "word_accuracy": round(1 - err / max(ref_n, 1), 4),
        "char_error_rate": round(cer_err / max(cer_n, 1), 4),
        "mean_conf_correct_words": mean(correct_conf),
        "mean_conf_wrong_words": mean(wrong_conf),
        f"wrong_words_flagged_at_{thr}": round(wrong_flagged / wrong_total, 4) if wrong_total else None,
    }


def eval_math(items):
    exact = rendered = 0
    dist = tot = 0
    for it in items:
        out = recognize_equation(cv2.imread(it["image"]))
        pred, ref = squash(out["latex"]), squash(it["latex"])
        exact += pred == ref
        rendered += bool(out["latex"]) and validate_latex(out["latex"])
        dist += lev(ref, pred)
        tot += len(ref)
    n = max(len(items), 1)
    return {
        "samples": len(items),
        "exact_match": round(exact / n, 4),
        "render_rate": round(rendered / n, 4),
        "normalized_edit_distance": round(dist / max(tot, 1), 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", default="output/ocr_eval.json")
    ap.add_argument("--threshold", type=float, default=LOW_CONF_THRESHOLD)
    a = ap.parse_args()
    data = json.loads(Path(a.labels).read_text(encoding="utf-8"))
    report = {}
    if t := [d for d in data if d["type"] == "text"]:
        report["text"] = eval_text(t, a.threshold)
    if m := [d for d in data if d["type"] == "equation"]:
        report["math"] = eval_math(m)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
