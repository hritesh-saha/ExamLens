from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base

class Document(Base):
    __tablename__ = "Document"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type = Column(String, nullable=False)  # "lecture_board" or "question_paper"
    source_pages = Column(Integer, nullable=False)
    timestamp = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Topic(Base):
    __tablename__ = "Topic"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    topic_code = Column(String, unique=True, index=True, nullable=False) #topic code is unique and used for linking notes and questions
    name = Column(String, nullable=False)
    syllabus_unit = Column(String, nullable=False)

class Note(Base):
    __tablename__ = "Note"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("Document.id"), nullable=False)
    page = Column(Integer, nullable=False)
    lecture_date = Column(String, nullable=True)
    text = Column(String, nullable=True)
    latex = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)

# Link table for the many-to-many relationship between Notes and Topics
class NoteTopic(Base):
    __tablename__ = "NoteTopic"

    note_id = Column(Integer, ForeignKey("Note.id"), primary_key=True)
    topic_id = Column(Integer, ForeignKey("Topic.id"), primary_key=True)

class Question(Base):
    __tablename__ = "Question"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("Document.id"), nullable=False)
    page = Column(Integer, nullable=False)
    year = Column(Integer, nullable=True)
    exam_type = Column(String, nullable=True) # Added based on Member 3
    section = Column(String, nullable=True) # Added based on Member 3
    marks = Column(Integer, nullable=True)
    is_compulsory = Column(Boolean, nullable=True, default=False) # Added based on Member 3
    raw_text = Column(String, nullable=False) # Changed from text
    cleaned_text = Column(String, nullable=True) # Added for member 4's NLP output
    topic_id = Column(Integer, ForeignKey("Topic.id"), nullable=True)
    repeat_group_id = Column(Integer, nullable=True)

class Flashcard(Base):
    __tablename__ = "Flashcard"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("Note.id"), nullable=False)
    linked_question_id = Column(Integer, ForeignKey("Question.id"), nullable=True)