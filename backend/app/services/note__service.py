import os
from sqlalchemy.orm import Session
import google.generativeai as genai
from dotenv import load_dotenv
from app.database import engine
from app.models import Note

# Load environment variables from the .env file
load_dotenv()

class NoteStructurer:
    def __init__(self):
        # Explicitly fetch the key from the environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in the .env file.")
        
        genai.configure(api_key=api_key)
        
        self.system_prompt = (
            "You are an academic data structurer. Convert the provided raw OCR text "
            "into organized markdown. Use '##' for headings, '-' for bullets, and bold "
            "key terms. Correct obvious OCR artifacts but do not hallucinate external facts."
        )
        
        # gemini-1.5-flash is fast, free-tier eligible, and highly capable for text formatting
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=self.system_prompt
        )

    def structure_notes(self):
        with Session(engine) as session:
            # Query notes that have OCR text but no structured content yet
            unstructured_notes = session.query(Note).filter(
                Note.raw_text != None,
                Note.structured_content == None
            ).all()
            
            if not unstructured_notes:
                print("No notes available for structuring.")
                return

            print(f"Found {len(unstructured_notes)} notes. Sending to Gemini API...")
            updates = 0
            
            for note in unstructured_notes:
                try:
                    response = self.model.generate_content(
                        note.raw_text,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,
                        )
                    )
                    
                    # Write to the new column, preserving Member 2's raw_text
                    note.structured_content = response.text
                    updates += 1
                    print(f"  [Success] Structured Note ID: {note.id}")
                    
                except Exception as e:
                    print(f"  [Error] Failed Note ID {note.id}: {e}")

            session.commit()
            print(f"Structuring complete: {updates}/{len(unstructured_notes)} notes updated.")

if __name__ == "__main__":
    structurer = NoteStructurer()
    structurer.structure_notes()