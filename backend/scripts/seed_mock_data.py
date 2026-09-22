import json
import os
from sqlalchemy.orm import Session
from app.database import engine, Base
from app.models import Topic, Question, Document

def seed_data():
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)

    # 1. Seed dummy Document if not present
    doc = session.query(Document).filter_by(id=1).first()
    if not doc:
        doc = Document(id=1, type="question_paper", source_pages=2, file_path="uploads/sample_paper.pdf")
        session.add(doc)
        session.commit()

    # 2. Seed Topics
    topics_path = os.path.join("data", "syllabus_topics.json")
    if os.path.exists(topics_path):
        with open(topics_path, "r") as f:
            topics_data = json.load(f)
            for item in topics_data:
                existing = session.query(Topic).filter_by(topic_code=item["topic_code"]).first()
                if not existing:
                    topic = Topic(
                        topic_code=item["topic_code"],
                        name=item["name"],
                        syllabus_unit=item["syllabus_unit"]
                    )
                    session.add(topic)
        session.commit()
        print("Topics seeded successfully.")

    # 3. Seed Sample Questions
    questions_path = os.path.join("data", "sample_questions.json")
    if os.path.exists(questions_path):
        with open(questions_path, "r") as f:
            questions_data = json.load(f)
            for item in questions_data:
                q = Question(
                    document_id=item["document_id"],
                    page=item["page"],
                    year=item["year"],
                    exam_type=item["exam_type"],
                    section=item["section"],
                    marks=item["marks"],
                    is_compulsory=item["is_compulsory"],
                    raw_text=item["raw_text"],
                    cleaned_text=item["raw_text"],  # Default cleaned_text to raw_text for seed
                    topic_id=None,
                    repeat_group_id=None
                )
                session.add(q)
        session.commit()
        print("Sample questions seeded successfully.")

    session.close()

if __name__ == "__main__":
    seed_data()