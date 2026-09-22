from pydantic import BaseModel
from typing import Optional, List

class SharedPageContract(BaseModel):
    document_id: int
    page_number: int
    doc_type: str
    image_path: str
    embedded_text: Optional[str] = None
    timestamp: Optional[str] = None

class DocumentResponse(BaseModel):
    id: int
    type: str
    source_pages: int
    timestamp: Optional[str]
    file_path: str

    class Config:
        from_attributes = True

class PageReorderRequest(BaseModel):
    new_page_order: List[int]

class NoteCreate(BaseModel):
    document_id: int
    page: int
    lecture_date: Optional[str] = None
    topic_ids: Optional[List[int]] = []  
    text: Optional[str] = None
    latex: Optional[str] = None
    confidence: Optional[float] = None

class QuestionCreate(BaseModel):
    document_id: int
    page: int
    year: Optional[int] = None
    marks: Optional[int] = None
    text: str
    topic_id: Optional[int] = None
    repeat_group_id: Optional[int] = None

class FlashcardCreate(BaseModel):
    note_id: int
    linked_question_id: Optional[int] = None