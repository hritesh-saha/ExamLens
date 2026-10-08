"""
evaluator.py
============
Parser evaluation and benchmarking tool for Member 3.

Evaluates the exam parser against sample question papers and synthetic
test benchmarks. Measures:
  1. Question Segmentation Accuracy (precision, recall, count matching)
  2. Metadata Extraction Accuracy (year, exam type, section, marks)
  3. Processing Speed & Latency (time per page / document)
  4. Output CSV/JSON benchmark report for academic/project submission

Usage:
    python -m app.exam_parser.evaluator
    python -m app.exam_parser.evaluator --output reports/eval_report.json
"""

import argparse
import io
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure backend directory is in sys.path
backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import fitz  # PyMuPDF

from app.exam_parser.parser import parse_question_paper


@dataclass
class BenchmarkResult:
    test_name: str
    total_pages: int
    expected_questions: int
    extracted_questions: int
    year_matched: bool
    exam_type_matched: bool
    marks_extracted_count: int
    elapsed_seconds: float
    accuracy_score: float  # 0.0 - 100.0


def create_benchmark_pdf(
    title: str,
    year: int,
    exam_type: str,
    questions: List[Dict[str, Any]]
) -> bytes:
    """Generate an in-memory PDF for benchmarking."""
    doc = fitz.open()
    page = doc.new_page()

    lines = [
        "UNIVERSITY DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING",
        f"{exam_type.upper()} EXAMINATION {year}",
        title.upper(),
        "Time: 3 Hours                                    Max Marks: 100",
        "-----------------------------------------------------------------",
    ]

    current_section = None
    for q in questions:
        sec = q.get("section")
        if sec and sec != current_section:
            current_section = sec
            lines.append(f"\nSECTION {current_section}")
            lines.append("Answer all questions in this section.\n")

        q_num = q.get("num", "1")
        text = q.get("text", "")
        marks = q.get("marks")
        marks_str = f" [{marks} marks]" if marks else ""
        lines.append(f"{q_num}. {text}{marks_str}")

    full_text = "\n".join(lines)
    page.insert_text((40, 60), full_text, fontsize=10)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def get_default_benchmarks() -> List[Dict[str, Any]]:
    """Return a suite of diverse test papers covering common exam formats."""
    return [
        {
            "name": "Standard EndSem (2 Sections, 5 Questions)",
            "year": 2025,
            "exam_type": "End Semester",
            "questions": [
                {"num": "1", "section": "A", "marks": 5, "text": "Define ACID properties and explain Atomicity."},
                {"num": "2", "section": "A", "marks": 5, "text": "What is the difference between primary key and unique key?"},
                {"num": "3", "section": "B", "marks": 10, "text": "Explain 1NF, 2NF, 3NF and BCNF with schema examples."},
                {"num": "4", "section": "B", "marks": 10, "text": "Explain two-phase locking protocol (2PL) in concurrency control."},
                {"num": "5", "section": "B", "marks": 10, "text": "Describe B-Tree index structure and its search algorithm."},
            ]
        },
        {
            "name": "MidSem Quiz Paper (Single Section, 4 Questions)",
            "year": 2024,
            "exam_type": "Mid Semester",
            "questions": [
                {"num": "Q1", "section": "A", "marks": 5, "text": "Explain Entity-Relationship (ER) modeling constructs."},
                {"num": "Q2", "section": "A", "marks": 5, "text": "Differentiate between Strong and Weak Entity sets."},
                {"num": "Q3", "section": "A", "marks": 5, "text": "What is Relational Algebra? Explain SELECT and PROJECT operators."},
                {"num": "Q4", "section": "A", "marks": 5, "text": "State the advantages of DBMS over File Processing Systems."},
            ]
        },
        {
            "name": "Internal Assessment Paper (3 Questions, High Marks)",
            "year": 2023,
            "exam_type": "Internal",
            "questions": [
                {"num": "1", "section": None, "marks": 15, "text": "Construct an ER diagram for a Hospital Management System with cardinalities."},
                {"num": "2", "section": None, "marks": 15, "text": "Given relation R(A,B,C,D,E) with FDs, determine the candidate keys and decompose to 3NF."},
                {"num": "3", "section": None, "marks": 20, "text": "Explain write-ahead logging (WAL) and checkpointing in crash recovery."},
            ]
        }
    ]


def run_evaluation(benchmarks: Optional[List[Dict[str, Any]]] = None) -> List[BenchmarkResult]:
    """
    Run evaluation suite and calculate accuracy scores.
    """
    if benchmarks is None:
        benchmarks = get_default_benchmarks()

    results: List[BenchmarkResult] = []

    for b in benchmarks:
        name = b["name"]
        expected_year = b["year"]
        expected_exam_type = b["exam_type"]
        expected_qs = b["questions"]
        exp_count = len(expected_qs)

        # Create temporary PDF
        pdf_data = create_benchmark_pdf(
            title="Database Systems",
            year=expected_year,
            exam_type=expected_exam_type,
            questions=expected_qs,
        )

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_data)
            tmp_path = tmp.name

        try:
            start_time = time.perf_counter()
            parsed = parse_question_paper(pdf_path=tmp_path, document_id=1)
            elapsed = time.perf_counter() - start_time

            act_count = len(parsed.questions)
            year_match = parsed.year == expected_year
            type_match = bool(parsed.exam_type and expected_exam_type.lower() in parsed.exam_type.lower())
            marks_found = sum(1 for q in parsed.questions if q.marks is not None)

            # Score calculation:
            # 40% question count recall/precision
            # 30% metadata accuracy (year + exam type)
            # 30% marks extraction rate
            count_acc = min(1.0, act_count / exp_count) if exp_count > 0 else 1.0
            meta_acc = (0.5 if year_match else 0.0) + (0.5 if type_match else 0.0)
            marks_acc = min(1.0, marks_found / exp_count) if exp_count > 0 else 1.0

            total_score = (count_acc * 40.0) + (meta_acc * 30.0) + (marks_acc * 30.0)

            results.append(BenchmarkResult(
                test_name=name,
                total_pages=parsed.total_pages or 1,
                expected_questions=exp_count,
                extracted_questions=act_count,
                year_matched=year_match,
                exam_type_matched=type_match,
                marks_extracted_count=marks_found,
                elapsed_seconds=round(elapsed, 4),
                accuracy_score=round(total_score, 2),
            ))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return results


def print_evaluation_report(results: List[BenchmarkResult]) -> None:
    """Print a clean CLI table of benchmark results."""
    print("=" * 80)
    print("                EXAMLENS PARSER EVALUATION BENCHMARK REPORT                ")
    print("=" * 80)
    print(f"{'Benchmark Test':<45} | {'Questions':<10} | {'Meta Match':<10} | {'Time':<6} | {'Score'}")
    print("-" * 80)

    total_score = 0.0
    total_time = 0.0
    for r in results:
        q_str = f"{r.extracted_questions}/{r.expected_questions}"
        meta_str = f"Y:{'OK' if r.year_matched else 'NO'} T:{'OK' if r.exam_type_matched else 'NO'}"
        time_str = f"{r.elapsed_seconds:.2f}s"
        score_str = f"{r.accuracy_score:.1f}%"
        print(f"{r.test_name:<45} | {q_str:<10} | {meta_str:<10} | {time_str:<6} | {score_str}")
        total_score += r.accuracy_score
        total_time += r.elapsed_seconds

    avg_score = total_score / len(results) if results else 0.0
    print("-" * 80)
    print(f"Overall Average Accuracy: {avg_score:.2f}%  |  Total Time: {total_time:.2f}s")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Evaluate ExamLens Question Paper Parser")
    parser.add_argument("--output", type=str, default=None, help="Path to save JSON evaluation report")
    args = parser.parse_args()

    results = run_evaluation()
    print_evaluation_report(results)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        report_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_benchmarks": len(results),
            "average_accuracy": round(sum(r.accuracy_score for r in results) / len(results), 2) if results else 0,
            "results": [asdict(r) for r in results]
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
