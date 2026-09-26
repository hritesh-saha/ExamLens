import os
from sqlalchemy.orm import Session
from openai import OpenAI
from app.database import engine
from app.models import Note

class NoteStructurer:
    def __init__(self):
        # Expects OPENAI_API_KEY in your environment variables
        self.client = OpenAI()
        self.system_prompt = (
            "You are an academic data structurer. Convert the provided raw OCR text "
            "into organized markdown. Use '##' for headings, '-' for bullets, and bold "
            "key terms. Correct obvious OCR artifacts but do not hallucinate external facts."
        )

    def structure_notes(self):
        with Session(engine) as session:
            # Query notes that contain text. 
            unstructured_notes = session.query(Note).filter(Note.text != None).all()
            
            if not unstructured_notes:
                print("No notes available for structuring.")
                return

            print(f"Found {len(unstructured_notes)} notes. Sending to LLM...")
            updates = 0
            
            for note in unstructured_notes:
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": note.text}
                        ],
                        temperature=0.1
                    )
                    
                    # CRITICAL: Overwriting the text field destroys original OCR data.
                    note.text = response.choices[0].message.content
                    updates += 1
                    print(f"  [Success] Structured Note ID: {note.id}")
                    
                except Exception as e:
                    print(f"  [Error] Failed Note ID {note.id}: {e}")

            session.commit()
            print(f"Structuring complete: {updates}/{len(unstructured_notes)} notes updated.")

if __name__ == "__main__":
    structurer = NoteStructurer()
    structurer.structure_notes()