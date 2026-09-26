import os
from collections import defaultdict
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer, util
from app.database import engine
from app.models import Question

class RepeatDetector:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', threshold: float = 0.70):
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold

    def detect_repeats(self):
        with Session(engine) as session:
            # 1. Fetch only questions that have been assigned a topic
            assigned_questions = session.query(Question).filter(Question.topic_id != None).all()
            if not assigned_questions:
                print("No assigned questions found for repeat detection.")
                return

            # 2. Partition questions by topic_id to reduce computational complexity
            topic_groups = defaultdict(list)
            for q in assigned_questions:
                topic_groups[q.topic_id].append(q)

            # Determine the current maximum repeat_group_id to prevent collision on subsequent runs
            max_group_record = session.query(Question).filter(Question.repeat_group_id != None).order_by(Question.repeat_group_id.desc()).first()
            current_group_id = max_group_record.repeat_group_id if (max_group_record and max_group_record.repeat_group_id) else 0

            updates = 0

            # 3. Process each topic partition independently
            for topic_id, questions in topic_groups.items():
                n = len(questions)
                if n < 2:
                    continue
                
                print(f"Processing Topic ID {topic_id} with {n} questions...")
                q_texts = [q.cleaned_text or q.raw_text for q in questions]
                embeddings = self.model.encode(q_texts, convert_to_tensor=True)
                
                # Compute pairwise cosine similarity matrix
                cosine_scores = util.cos_sim(embeddings, embeddings)
                
                # 4. Build adjacency list for graph clustering
                adj_list = defaultdict(list)
                for i in range(n):
                    for j in range(i + 1, n):
                        score = cosine_scores[i][j].item()
                        if score >= self.threshold:
                            adj_list[i].append(j)
                            adj_list[j].append(i)
                            print(f"  [Edge] Q ID {questions[i].id} & Q ID {questions[j].id} (Score: {score:.3f})")
                            
                # 5. Extract connected components using BFS
                visited = set()
                for i in range(n):
                    if i not in visited and i in adj_list:
                        component = []
                        queue = [i]
                        visited.add(i)
                        
                        while queue:
                            node = queue.pop(0)
                            component.append(node)
                            for neighbor in adj_list[node]:
                                if neighbor not in visited:
                                    visited.add(neighbor)
                                    queue.append(neighbor)
                        
                        # Apply group ID if the component qualifies as a repeat cluster
                        if len(component) >= 2:
                            current_group_id += 1
                            for node_idx in component:
                                q = questions[node_idx]
                                q.repeat_group_id = current_group_id
                                updates += 1
                            print(f"  -> Created Repeat Group {current_group_id} with {len(component)} questions.")

            session.commit()
            print(f"Repeat detection complete. Assigned repeat_group_id to {updates} questions.")

if __name__ == "__main__":
    detector = RepeatDetector()
    detector.detect_repeats()