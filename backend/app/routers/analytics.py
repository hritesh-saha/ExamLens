from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd
from app.database import engine, get_db
from analytics_and_planning.member5_analytics import get_coverage_gaps, generate_study_plan

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/coverage")
def get_coverage(db: Session = Depends(get_db)):
    """Passes DB tables to Analytics Lead's coverage function."""
    try:
        topics_df = pd.read_sql("SELECT * FROM Topic", engine)
        notes_df = pd.read_sql("SELECT * FROM Note", engine)
        questions_df = pd.read_sql("SELECT * FROM Question", engine)
        note_topics_df = pd.read_sql("SELECT * FROM NoteTopic", engine)

        result = get_coverage_gaps(topics_df, notes_df, questions_df, note_topics_df)
        return result
    except ValueError as e:
        # e.g. no questions with a year yet -- not a server error, just "nothing to report"
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/planner")
def generate_plan(days_left: int, hours_per_day: float, db: Session = Depends(get_db)):
    """Passes DB tables to Analytics Lead's study planner function."""
    try:
        topics_df = pd.read_sql("SELECT * FROM Topic", engine)
        questions_df = pd.read_sql("SELECT * FROM Question", engine)
        notes_df = pd.read_sql("SELECT * FROM Note", engine)
        note_topics_df = pd.read_sql("SELECT * FROM NoteTopic", engine)

        result = generate_study_plan(topics_df, questions_df, days_left, hours_per_day,
                                     notes_df, note_topics_df)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
