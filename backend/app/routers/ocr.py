"""Member 2 routes: review queue + corrections for the edit UI.

Register in main.py:
    from app.routers.ocr import router as ocr_router
    app.include_router(ocr_router)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.ocr.models import CorrectionRequest, PageOCRResult
from app.ocr.store import list_pages, load_result, save_result, upsert_note

router = APIRouter(prefix="/api/ocr", tags=["OCR & Math"])


@router.get("/{document_id}/pages/{page}", response_model=PageOCRResult)
def get_page(document_id: int, page: int):
    res = load_result(document_id, page)
    if res is None:
        raise HTTPException(404, "No OCR result for this page")
    return res


@router.get("/{document_id}/review")
def review_queue(document_id: int):
    """Everything needing a human look, lowest confidence first."""
    items = []
    for pg in list_pages(document_id):
        res = load_result(document_id, pg)
        for b in res.text_blocks:
            items += [
                {"kind": "word", "page": pg, "id": w.word_id, "text": w.text,
                 "confidence": w.confidence, "box": [w.x, w.y, w.w, w.h]}
                for w in b.words if w.low_confidence
            ]
        items += [
            {"kind": "equation", "page": pg, "id": e.region_id, "latex": e.latex,
             "confidence": e.confidence, "render_ok": e.render_ok,
             "box": [e.x, e.y, e.width, e.height]}
            for e in res.equations if e.low_confidence
        ]
    items.sort(key=lambda i: i["confidence"])
    return {"document_id": document_id, "count": len(items), "items": items}


@router.put("/{document_id}/pages/{page}/corrections", response_model=PageOCRResult)
def apply_corrections(document_id: int, page: int, body: CorrectionRequest,
                      db: Session = Depends(get_db)):
    from app.ocr.math_ocr import validate_latex
    res = load_result(document_id, page)
    if res is None:
        raise HTTPException(404, "No OCR result for this page")

    words = {w.word_id: w for b in res.text_blocks for w in b.words}
    for c in body.words:
        if c.word_id not in words:
            raise HTTPException(422, f"Unknown word_id {c.word_id}")
        w = words[c.word_id]
        w.text, w.confidence, w.corrected = c.text.strip(), 1.0, True

    eqs = {e.region_id: e for e in res.equations}
    for c in body.equations:
        if c.region_id not in eqs:
            raise HTTPException(422, f"Unknown equation {c.region_id}")
        e = eqs[c.region_id]
        e.latex, e.confidence, e.corrected = c.latex.strip(), 1.0, True
        e.render_ok = validate_latex(e.latex)

    res.rebuild()
    save_result(res)
    upsert_note(db, res)
    db.commit()
    return res
