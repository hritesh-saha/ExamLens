"""
loader.py
=========
Syllabus CSV loader for ExamLens.

Loads syllabus topics from a CSV file into the `topics` SQLite table.
Member 4 uses the loaded topics to classify questions by topic.

CSV format expected:
    topic_code,name,syllabus_unit
    DBMS-01,Database System Architecture and Concepts,Unit 1
    DBMS-02,Entity-Relationship (ER) Data Model,Unit 1

Also supports case-insensitive and flexible column naming:
    - topic_code / code / id
    - name / topic_name / topic / title
    - syllabus_unit / unit / module / chapter
"""

import argparse
import csv
import io
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.database.db import get_all_topics, init_db, insert_topics_batch
from app.exam_parser.models import Topic


def _normalize_header(header: str) -> str:
    """Normalize header string for fuzzy column mapping."""
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def _find_column_key(row_keys: List[str], candidates: List[str]) -> Optional[str]:
    """Find the key in row_keys that matches one of the candidate names."""
    norm_map = {_normalize_header(k): k for k in row_keys}
    for cand in candidates:
        if cand in norm_map:
            return norm_map[cand]
    return None


def parse_syllabus_csv(csv_content: Union[str, io.StringIO, Path]) -> List[Topic]:
    """
    Parse CSV text or filepath into a list of validated Topic models.

    Args:
        csv_content: File path, string content, or StringIO buffer.

    Returns:
        List[Topic]: Validated Topic instances.

    Raises:
        ValueError: If required columns cannot be found or content is invalid.
    """
    if isinstance(csv_content, (str, Path)) and os.path.exists(str(csv_content)):
        with open(str(csv_content), mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    elif isinstance(csv_content, (str, io.StringIO)):
        f = io.StringIO(csv_content) if isinstance(csv_content, str) else csv_content
        reader = csv.DictReader(f)
        rows = list(reader)
    else:
        raise ValueError(f"Invalid csv_content input: {csv_content}")

    if not rows:
        return []

    fieldnames = reader.fieldnames or []
    code_col = _find_column_key(fieldnames, ["topic_code", "code", "id", "topic_id"])
    name_col = _find_column_key(fieldnames, ["name", "topic_name", "topic", "title", "description"])
    unit_col = _find_column_key(fieldnames, ["syllabus_unit", "unit", "module", "chapter", "section"])

    if not code_col or not name_col or not unit_col:
        missing = []
        if not code_col: missing.append("topic_code")
        if not name_col: missing.append("name")
        if not unit_col: missing.append("syllabus_unit")
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}. Found: {fieldnames}")

    topics: List[Topic] = []
    for i, row in enumerate(rows, start=2):  # row 2 in CSV is first data row
        code = (row.get(code_col) or "").strip()
        name = (row.get(name_col) or "").strip()
        unit = (row.get(unit_col) or "").strip()

        if not code or not name or not unit:
            continue  # Skip empty or partial rows

        topic = Topic(
            topic_code=code,
            name=name,
            syllabus_unit=unit,
        )
        topics.append(topic)

    return topics


def load_syllabus_to_db(
    csv_path_or_content: Union[str, io.StringIO, Path],
    db_path: Optional[str] = None
) -> int:
    """
    Parse a CSV and insert all valid topics into the SQLite database.

    Args:
        csv_path_or_content: Path to CSV or string content.
        db_path: Path to database. If not provided, uses default DB.

    Returns:
        int: Number of topics loaded.
    """
    topics = parse_syllabus_csv(csv_path_or_content)
    if not topics:
        return 0

    init_db(db_path)
    return insert_topics_batch(topics, db_path=db_path)


def main():
    """CLI entry point: python -m app.syllabus.loader --csv <path> [--db <path>]"""
    parser = argparse.ArgumentParser(description="Load syllabus CSV into ExamLens database.")
    parser.add_argument(
        "--csv",
        type=str,
        default=str(Path(__file__).parent / "sample_syllabus.csv"),
        help="Path to the syllabus CSV file."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite database file (optional)."
    )
    args = parser.parse_args()

    csv_file = Path(args.csv)
    if not csv_file.exists():
        print(f"Error: File not found: {csv_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading syllabus from {csv_file} ...")
    count = load_syllabus_to_db(csv_file, db_path=args.db)
    print(f"Successfully loaded {count} topics into database.")

    topics = get_all_topics(db_path=args.db)
    print("\nCurrent database topics:")
    for t in topics:
        print(f"  [{t['topic_code']}] {t['syllabus_unit']}: {t['name']}")


if __name__ == "__main__":
    main()
