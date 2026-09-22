"""
generate_sample_pdf.py
======================
Generates a realistic sample university question paper PDF for testing.
"""

from pathlib import Path
import fitz  # PyMuPDF

output_path = Path(__file__).resolve().parent.parent / "sample_exam_paper.pdf"

doc = fitz.open()

# Page 1
page1 = doc.new_page()
content_p1 = """UNIVERSITY OF COMPUTER SCIENCE & ENGINEERING
End Semester Examination - November 2025
Subject: Database Management Systems (CS-302)

Time Allowed: 3 Hours                                  Maximum Marks: 100
-------------------------------------------------------------------------
Instructions:
1. Section A is compulsory (Answer all questions).
2. Section B: Answer any FOUR questions out of six.
3. Figures to the right indicate full marks.
-------------------------------------------------------------------------

SECTION A (20 Marks)
Answer all questions. Each carries 5 marks.

Q1. Explain the three-level ANSI/SPARC database architecture with a neat diagram. [5 marks]

Q2. Define Super Key, Candidate Key, and Primary Key with suitable examples. [5 marks]

Q3. What are ACID properties? Explain the significance of Durability in DBMS. [5 marks]

Q4. Differentiate between file-based systems and DBMS. [5 marks]


SECTION B (80 Marks)
Answer any FOUR questions. Each question carries 20 marks.

Q5. (a) What is Normalization? Explain 1NF, 2NF, and 3NF with examples. [10 marks]
    (b) When is a relation considered in BCNF? Differentiate 3NF from BCNF. [10 marks]
"""
page1.insert_text((40, 50), content_p1, fontsize=10)

# Page 2
page2 = doc.new_page()
content_p2 = """SECTION B (Continued)

Q6. Construct an Entity-Relationship (ER) diagram for an Online University Library Management System. Specify entity sets, relationships, key attributes, and mapping cardinalities clearly. [20 marks]

Q7. (a) What is Relational Algebra? Explain SELECT, PROJECT, and CARTESIAN PRODUCT operations. [10 marks]
    (b) Write SQL queries for a relation Student(RollNo, Name, Department, Marks):
        (i) List all students with marks greater than 75 in CSE. [5 marks]
        (ii) Find the average marks per department. [5 marks]

Q8. Explain the Two-Phase Locking (2PL) protocol. How does it prevent concurrency anomalies? Differentiate between Strict 2PL and Rigorous 2PL. [20 marks]
"""
page2.insert_text((40, 50), content_p2, fontsize=10)

doc.save(str(output_path))
doc.close()
print(f"Sample exam paper created at: {output_path}")
