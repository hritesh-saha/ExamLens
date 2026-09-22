import os
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer, util
from app.database import engine
from app.models import Topic, Question

class TopicAssigner:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', threshold: float = 0.45):
        print(f"Loading embedding model '{model_name}'...")
        # Suppress symlink warnings on Windows
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        self.topic_embeddings = None
        self.topic_map = {}  # Maps tensor index back to the integer Topic.id

    def _load_and_embed_topics(self, session: Session) -> bool:
        topics = session.query(Topic).all()
        if not topics:
            print("Error: No topics found in the database.")
            return False

        topic_texts = []
        for idx, t in enumerate(topics):
            # Concatenate name and unit for a denser semantic representation
            text = f"{t.name}. {t.syllabus_unit}"
            topic_texts.append(text)
            self.topic_map[idx] = t.id

        print(f"Embedding {len(topic_texts)} syllabus topics...")
        self.topic_embeddings = self.model.encode(topic_texts, convert_to_tensor=True)
        return True

    def assign_topics_to_questions(self):
        with Session(engine) as session:
            if not self._load_and_embed_topics(session):
                return

            # Target only questions without a designated topic
            unassigned_questions = session.query(Question).filter(Question.topic_id == None).all()
            if not unassigned_questions:
                print("No unassigned questions found.")
                return

            print(f"Processing {len(unassigned_questions)} unassigned questions...")
            
            # Batch encode question texts (fallback to raw_text if cleaned_text is unavailable)
            q_texts = [q.cleaned_text or q.raw_text for q in unassigned_questions]
            q_embeddings = self.model.encode(q_texts, convert_to_tensor=True)

            # Compute dot product/cosine similarity matrix
            cosine_scores = util.cos_sim(q_embeddings, self.topic_embeddings)

            updates = 0
            for i, q in enumerate(unassigned_questions):
                scores = cosine_scores[i]
                best_score_val = scores.max().item()
                best_idx = scores.argmax().item()

                if best_score_val >= self.threshold:
                    q.topic_id = self.topic_map[best_idx]
                    updates += 1
                    print(f"[Match] Q ID: {q.id} -> Topic ID: {q.topic_id} (Confidence: {best_score_val:.3f})")
                else:
                    print(f"[Skip] Q ID: {q.id} remains NULL (Highest confidence: {best_score_val:.3f} < {self.threshold})")

            session.commit()
            print(f"Update complete: Assigned topics to {updates}/{len(unassigned_questions)} questions.")

if __name__ == "__main__":
    assigner = TopicAssigner()
    assigner.assign_topics_to_questions()