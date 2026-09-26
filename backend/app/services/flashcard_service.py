import csv
import os
from sqlalchemy.orm import Session
from app.database import engine
from app.models import Note, Flashcard, Question, NoteTopic

class FlashcardGenerator:
    def __init__(self, export_dir: str = "exports"):
        self.export_dir = export_dir
        if not os.path.exists(self.export_dir):
            os.makedirs(self.export_dir)

    def generate_from_notes(self):
        with Session(engine) as session:
            # Fetch notes that have been structured by the LLM (Phase 4)
            # Note: Update this to filter by structured_content once your models.py is updated
            notes = session.query(Note).filter(Note.text != None).all()
            
            if not notes:
                print("No structured notes found to generate flashcards.")
                return

            updates = 0
            
            for note in notes:
                # 1. Very basic extraction logic (In reality, use the LLM or regex on your markdown)
                # This assumes your LLM structured the text with "Q: ... A: ..." or similar bullets
                lines = note.text.split('\n')
                front_text = f"Key concept from page {note.page}"
                back_text = " ".join(lines[:2]) # Dummy extraction for prototype
                
                # 2. Find a related past exam question to link (Phase 2 & 3 integration)
                linked_q_id = None
                note_topic = session.query(NoteTopic).filter_by(note_id=note.id).first()
                
                if note_topic:
                    # Find a past question that shares this topic and has been asked frequently
                    related_q = session.query(Question).filter(
                        Question.topic_id == note_topic.topic_id,
                        Question.repeat_group_id != None
                    ).first()
                    
                    if related_q:
                        linked_q_id = related_q.id
                        back_text += f"\n\n[Past Exam Context]: {related_q.raw_text}"

                # 3. Create the flashcard
                card = Flashcard(
                    note_id=note.id,
                    front=front_text,
                    back=back_text,
                    linked_question_id=linked_q_id
                )
                session.add(card)
                updates += 1

            session.commit()
            print(f"Generated {updates} flashcards in the database.")

    def export_to_anki(self):
        with Session(engine) as session:
            cards = session.query(Flashcard).all()
            if not cards:
                print("No flashcards to export.")
                return
                
            filepath = os.path.join(self.export_dir, "anki_deck.csv")
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Front", "Back", "Tags"])
                
                for card in cards:
                    # Get topics to use as Anki tags
                    tags = "study_platform"
                    note_topics = session.query(NoteTopic).filter_by(note_id=card.note_id).all()
                    if note_topics:
                        tags += " " + " ".join([f"topic_{nt.topic_id}" for nt in note_topics])
                        
                    writer.writerow([card.front, card.back.replace('\n', '<br>'), tags])
                    
            print(f"Exported {len(cards)} cards to {filepath} for Anki import.")

if __name__ == "__main__":
    generator = FlashcardGenerator()
    generator.generate_from_notes()
    generator.export_to_anki()