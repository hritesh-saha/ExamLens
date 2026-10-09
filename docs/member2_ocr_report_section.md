# Section: OCR and Math Recognition (Member 2)

## 1. Objective
Convert cleaned lecture-board pages (from the Vision stage) into machine-readable text with word-level
confidence, and equation regions into LaTeX, so that low-quality output is visible and correctable.

## 2. Pipeline
Cleaned page + regions (Member 1) -> per-region routing -> text OCR / equation OCR -> confidence + validation
-> page result (JSON sidecar) -> Note row (text, latex, confidence) -> review queue and correction API.

| Stage | Method | Output |
|---|---|---|
| Preprocess | grayscale, auto-invert dark boards, pad, upscale small crops | OCR-ready crop |
| Text OCR | Tesseract (word-level conf) or EasyOCR (line conf shared by words) | words + box + confidence |
| Equation OCR | pix2tex (LatexOCR) | LaTeX string |
| Math validation | matplotlib mathtext parse; structural check for matrix/cases/align | render_ok flag |
| Math confidence | agreement between predictions on original and 1.25x crop; capped at 0.30 if LaTeX does not render | 0-1 score |
| Flagging | word/equation below threshold (default 0.60) or non-rendering LaTeX | low_confidence |
| Correction | PUT corrections; corrected items set to confidence 1.0, Note rebuilt | updated Note |

## 3. Design decisions (justify in viva)
- Word-level confidence is native to Tesseract; EasyOCR is offered because it is stronger on handwriting.
- pix2tex exposes no probability, so confidence is a documented proxy (self-agreement + render validity).
- Word boxes are stored in a JSON sidecar, not the DB, to avoid changing the shared schema.
- A failed page never stops the batch; no-region pages fall back to full-page OCR.

## 4. Interface
- `run_ocr_and_math(cleaned_pages) -> list[PageOCRResult]`; `run_and_store(cleaned_pages, db, lecture_date)`
- `GET /api/ocr/{doc}/pages/{page}`, `GET /api/ocr/{doc}/review`, `PUT /api/ocr/{doc}/pages/{page}/corrections`

## 5. Evaluation (fill from `python -m scripts.eval_ocr`)
Sample: __ text regions (__ words) from __ real board photos; __ equations. Hand-labeled by Member 2.

| Metric | Value |
|---|---|
| Word accuracy (1 - WER) | __ |
| Character error rate | __ |
| Mean confidence, correct words | __ |
| Mean confidence, wrong words | __ |
| Wrong words caught by low-confidence flag (thr 0.60) | __ |
| Equation exact match | __ |
| LaTeX render rate | __ |
| Normalized edit distance | __ |

Also report: Tesseract vs EasyOCR comparison on the same sample; 2-3 failure cases with screenshots
(glare, cursive, tiny subscripts); effect of the confidence threshold (0.5 / 0.6 / 0.7).

## 6. Limitations / future work
Handwriting variance, multi-line equations split into several regions, no per-token math confidence,
no spell-correction (handled by Member 4's LLM structuring step).

---
# Report Lead checklist (whole project)
- Skeleton: Abstract, Introduction, Related Work, System Design, Per-module sections (6), Integration,
  Evaluation summary, Limitations/Future Work, Conclusion, References.
- Collect from each member by end of Week 2: 1 metric table + 2 screenshots + 3 failure cases + 5 references.
- Metric owners: M1 board detection success rate, M2 above, M3 segmentation accuracy on 5+ papers,
  M4 topic accuracy and repeat precision/recall, M5 planner/practice-set sanity + back-test, M6 end-to-end time.
- Freeze text at end of Week 3 minus 2 days; unfinished features go to Future Work.
