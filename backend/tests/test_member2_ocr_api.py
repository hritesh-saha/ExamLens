from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.ocr import store
from app.ocr.models import EquationResult, OCRWord, PageOCRResult, TextBlockResult
from app.routers.ocr import router


def test_review_and_correction(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "OUTPUT_ROOT", tmp_path)
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)

    app = FastAPI()
    app.include_router(router)
    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()
    app.dependency_overrides[get_db] = _db

    res = PageOCRResult(
        document_id=1, page_number=1,
        text_blocks=[TextBlockResult(region_id="r", x=0, y=0, width=9, height=9, words=[
            OCRWord(word_id="r:0", text="ecuals", confidence=0.2, x=0, y=0, w=5, h=5)])],
        equations=[EquationResult(region_id="e", x=0, y=20, width=9, height=9,
                                  latex=r"\frac{a", confidence=0.2, render_ok=False)],
    )
    res.rebuild()
    store.save_result(res)

    c = TestClient(app)
    q = c.get("/api/ocr/1/review").json()
    assert q["count"] == 2
    r = c.put("/api/ocr/1/pages/1/corrections", json={
        "words": [{"word_id": "r:0", "text": "equals"}],
        "equations": [{"region_id": "e", "latex": r"\frac{a}{b}"}]})
    assert r.status_code == 200, r.text
    assert c.get("/api/ocr/1/review").json()["count"] == 0
    note = Session().query(models.Note).filter_by(document_id=1, page=1).first()
    assert "equals" in note.text and note.latex == r"\frac{a}{b}"
