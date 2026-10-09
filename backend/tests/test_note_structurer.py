"""Unit tests for Gemini note structuring. No live API calls."""

import pytest

from app.models import Note
from app.services.note__service import (
    GeminiNotConfiguredError,
    GeminiResponseError,
    NoteStructurer,
    gemini_key_is_configured,
)


def test_missing_gemini_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(GeminiNotConfiguredError, match="GEMINI_API_KEY"):
        NoteStructurer(api_key="")


def test_placeholder_key_is_rejected(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    assert gemini_key_is_configured() is False
    with pytest.raises(GeminiNotConfiguredError):
        NoteStructurer()


def test_structure_text_uses_injected_generator(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-sent-to-network")
    structurer = NoteStructurer(
        api_key="test-key-not-sent-to-network",
        generate_fn=lambda text: f"## Cleaned\n- {text}",
    )
    assert structurer.structure_text("raw ocr") == "## Cleaned\n- raw ocr"


def test_empty_ocr_text_is_rejected(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-sent-to-network")
    structurer = NoteStructurer(
        api_key="test-key-not-sent-to-network",
        generate_fn=lambda text: "unused",
    )
    with pytest.raises(GeminiResponseError, match="empty"):
        structurer.structure_text("   ")


def test_empty_model_output_is_rejected(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-sent-to-network")
    structurer = NoteStructurer(
        api_key="test-key-not-sent-to-network",
        generate_fn=lambda text: "",
    )
    with pytest.raises(GeminiResponseError, match="empty structured"):
        structurer.structure_text("some ocr")


def test_structure_notes_persists_markdown(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.database import Base
    import app.models  # noqa: F401

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-sent-to-network")
    from app.models import Document

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    session.add(Document(id=1, type="lecture_board", file_name="n.pdf", source_pages=1, file_path="n.pdf"))
    session.add(Note(document_id=1, page=1, text="Force equals mass times acceleration"))
    session.commit()
    note_id = session.query(Note).one().id

    structurer = NoteStructurer(
        api_key="test-key-not-sent-to-network",
        generate_fn=lambda text: "## Newton's second law",
    )
    result = structurer.structure_notes(session=session, note_ids=[note_id])
    assert result["status"] == "ok"
    assert result["updated"] == 1
    stored = session.query(Note).one()
    assert stored.structured_content == "## Newton's second law"
    session.close()


@pytest.mark.skipif(
    not gemini_key_is_configured(),
    reason="GEMINI_API_KEY is not configured; live Gemini call skipped",
)
def test_live_gemini_structures_text():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.database import Base
    from app.models import Document

    structurer = NoteStructurer()
    out = structurer.structure_text("Newton second law F = ma")
    assert len(out) > 5
    assert "API_KEY" not in out.upper()

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    try:
        session.add(
            Document(
                id=1,
                type="lecture_board",
                file_name="n.pdf",
                source_pages=1,
                file_path="n.pdf",
            )
        )
        note = Note(
            document_id=1,
            page=1,
            text="Newton second law F = ma",
            structured_content=out,
        )
        session.add(note)
        session.commit()
        stored = session.query(Note).one()
        assert stored.structured_content == out
    finally:
        session.close()
