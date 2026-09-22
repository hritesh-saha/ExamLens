from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Document
from app.routers.documents import get_shared_contract_payload

# Teammate function placeholders
# from teammates.member1_vision import process_board_images
# from teammates.member2_ocr import run_ocr_and_math
# from teammates.member3_parsing import parse_exam_paper
# from teammates.member4_nlp import assign_topics_and_structure

router = APIRouter(prefix="/api/process", tags=["Processing Pipeline"])

@router.post("/{document_id}")
def trigger_processing_pipeline(document_id: int, db: Session = Depends(get_db)):
    """
    The main integration hub. Pulls the Shared Contract and routes it to the correct engines.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Generate the Day 1 Shared Contract (List of pages/images/text)
    shared_contract = get_shared_contract_payload(document_id, db)
    
    try:
        # 2. Route based on document type
        if doc.type == "lecture_board":
            # cleaned_pages = process_board_images(shared_contract)
            # ocr_results = run_ocr_and_math(cleaned_pages)
            # structured_notes = assign_topics_and_structure(ocr_results)
            # db.bulk_insert_mappings(Note, structured_notes)
            pass
        elif doc.type == "question_paper":
            # questions_data = parse_exam_paper(shared_contract)
            # tagged_questions = assign_topics_and_structure(questions_data)
            # db.bulk_insert_mappings(Question, tagged_questions)
            pass
            
        db.commit()
        return {"status": "success", "message": f"Pipeline completed for {doc.type}"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Pipeline failure: {str(e)}")