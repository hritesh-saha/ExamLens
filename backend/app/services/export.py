import io
import csv
from typing import List, Any, Tuple
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_markdown_export(notes: List[Any]) -> str:
    """Generates clean Markdown from Note database records."""
    md_content = "# ExamLens Notes Export\n\n"
    for note in notes:
        md_content += f"## Page {note.page}\n"
        if note.lecture_date:
            md_content += f"**Lecture Date:** {note.lecture_date}\n\n"
        if note.text:
            md_content += f"{note.text}\n\n"
        if note.latex:
            md_content += f"**Equations:**\n$$\n{note.latex}\n$$\n\n"
        md_content += "---\n\n"
    return md_content

def generate_pdf_export(notes: List[Any]) -> bytes:
    """Renders notes into a PDF document using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title_style = styles['Heading1']
    body_style = styles['BodyText']

    story.append(Paragraph("ExamLens Study Notes", title_style))
    story.append(Spacer(1, 12))

    for note in notes:
        story.append(Paragraph(f"Page {note.page}", styles['Heading2']))
        if note.lecture_date:
            story.append(Paragraph(f"Date: {note.lecture_date}", styles['Italic']))
        if note.text:
            story.append(Spacer(1, 6))
            story.append(Paragraph(note.text, body_style))
        if note.latex:
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"Math: {note.latex}", body_style))
        story.append(Spacer(1, 12))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def generate_anki_csv_export(flashcards: List[Tuple[Any, Any]]) -> str:
    """
    Generates an Anki-compatible CSV from Flashcard and Note tuples.
    Format: Front (Note/Question text), Back (Answer/Note text), Tags
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Front", "Back", "Tags"])

    for fc, note, question in flashcards:
        front = question.text if question else f"Note Review (Page {note.page})"
        back = note.text if note.text else ""
        if note.latex:
            back += f" [LaTeX: {note.latex}]"
        tags = "ExamLens StudyPlanner"
        writer.writerow([front, back, tags])

    return output.getvalue()