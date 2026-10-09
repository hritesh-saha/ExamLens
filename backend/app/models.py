from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Document(Base):
    __tablename__ = "Document"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type = Column(String, nullable=False)  # "lecture_board" or "question_paper"
    file_name = Column(String, nullable=True)  # required by Member 3 sqlite schema
    source_pages = Column(Integer, nullable=False)
    timestamp = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    exam_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Topic(Base):
    __tablename__ = "Topic"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    topic_code = Column(String, unique=True, index=True, nullable=False) 
    name = Column(String, nullable=False)
    syllabus_unit = Column(String, nullable=False)
    note_links = relationship("NoteTopic", back_populates="topic")

class Note(Base):
    __tablename__ = "Note"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("Document.id"), nullable=False)
    page = Column(Integer, nullable=False)
    lecture_date = Column(String, nullable=True)
    text = Column(String, nullable=True)
    structured_content = Column(String, nullable=True) # Required for LLM output
    latex = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    # Topics are mapped through NoteTopic, not a topic_ids column on this table.
    topic_links = relationship(
        "NoteTopic", back_populates="note", cascade="all, delete-orphan"
    )

# Link table for Member 4's many-to-many Note ↔ Topic mapping.
class NoteTopic(Base):
    __tablename__ = "NoteTopic"

    note_id = Column(Integer, ForeignKey("Note.id"), primary_key=True)
    topic_id = Column(Integer, ForeignKey("Topic.id"), primary_key=True)
    confidence = Column(Float, nullable=True)
    note = relationship("Note", back_populates="topic_links")
    topic = relationship("Topic", back_populates="note_links")

class Question(Base):
    __tablename__ = "Question"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("Document.id"), nullable=False)
    page = Column(Integer, nullable=False)
    year = Column(Integer, nullable=True)
    exam_type = Column(String, nullable=True) 
    section = Column(String, nullable=True) 
    marks = Column(Integer, nullable=True)
    is_compulsory = Column(Boolean, nullable=True, default=False) 
    text = Column(String, nullable=False) # Reverted from raw_text
    cleaned_text = Column(String, nullable=True) # Added for member 4's NLP output
    topic_id = Column(Integer, ForeignKey("Topic.id"), nullable=True)
    repeat_group_id = Column(Integer, nullable=True)

class Flashcard(Base):
    __tablename__ = "Flashcard"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("Note.id"), nullable=False)
    front = Column(String, nullable=False)
    back = Column(String, nullable=False)
    linked_question_id = Column(Integer, ForeignKey("Question.id"), nullable=True)