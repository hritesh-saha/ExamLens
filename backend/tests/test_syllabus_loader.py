"""
test_syllabus_loader.py
========================
Tests for syllabus loader (CSV parsing and database ingestion).
"""

import io
import os
import tempfile
import pytest
from app.syllabus.loader import parse_syllabus_csv, load_syllabus_to_db
from app.database.db import get_all_topics, init_db


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_parse_syllabus_csv_standard():
    csv_data = """topic_code,name,syllabus_unit
DBMS-01,Architecture,Unit 1
DBMS-02,ER Model,Unit 1
"""
    topics = parse_syllabus_csv(csv_data)
    assert len(topics) == 2
    assert topics[0].topic_code == "DBMS-01"
    assert topics[0].name == "Architecture"
    assert topics[0].syllabus_unit == "Unit 1"


def test_parse_syllabus_csv_flexible_headers():
    csv_data = """Code,Topic Name,Module
CS-101,Operating Systems,Module 1
CS-102,Memory Management,Module 2
"""
    topics = parse_syllabus_csv(csv_data)
    assert len(topics) == 2
    assert topics[0].topic_code == "CS-101"
    assert topics[0].name == "Operating Systems"
    assert topics[0].syllabus_unit == "Module 1"


def test_parse_syllabus_csv_missing_column():
    csv_data = """code,description
CS-101,Operating Systems
"""
    with pytest.raises(ValueError, match="CSV missing required columns"):
        parse_syllabus_csv(csv_data)


def test_parse_syllabus_empty():
    topics = parse_syllabus_csv("")
    assert topics == []


def test_load_syllabus_to_db(temp_db):
    sample_csv = os.path.join(
        os.path.dirname(__file__), "..", "app", "syllabus", "sample_syllabus.csv"
    )
    count = load_syllabus_to_db(sample_csv, db_path=temp_db)
    assert count == 10

    topics = get_all_topics(db_path=temp_db)
    assert len(topics) == 10
    assert any(t["topic_code"] == "DBMS-05" for t in topics)
