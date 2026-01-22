import sys
import os
import time
from sqlalchemy import event
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool
import uuid
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.review import ReviewTask, ReviewResultItem, TaskStatus, ResultCode
from backend.models.document import Document
from backend.models.rule import Rule, RuleGroup
from backend.models.comparison import ComparisonDocument, ComparisonResult
from backend.services.review_service import ReviewService

class QueryCounter:
    def __init__(self, engine):
        self.engine = engine
        self.count = 0
        self.queries = []

    def __enter__(self):
        self.count = 0
        self.queries = []
        event.listen(self.engine, "before_cursor_execute", self.callback)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        event.remove(self.engine, "before_cursor_execute", self.callback)

    def callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        # self.queries.append(statement)

def setup_db():
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine

def seed_data(session: Session, num_tasks=20, rules_per_task=20):
    owner_id = str(uuid.uuid4())
    
    # Create Documents and Rule Groups
    docs = []
    groups = []
    
    for i in range(5):
        doc = Document(filename=f"doc_{i}.pdf", content="test", status="DONE", owner_id=owner_id)
        session.add(doc)
        docs.append(doc)
        
        group = RuleGroup(name=f"group_{i}", description="test")
        session.add(group)
        groups.append(group)
    
    session.commit()
    for d in docs: session.refresh(d)
    for g in groups: session.refresh(g)

    # Create Rules
    rules = []
    for i in range(rules_per_task):
        rule = Rule(
            content=f"rule content {i}", 
            clause_number=f"1.{i}", 
            group_id=groups[i % len(groups)].id
        )
        session.add(rule)
        rules.append(rule)
    session.commit()
    for r in rules: session.refresh(r)

    # Create Tasks
    task_ids = []
    for i in range(num_tasks):
        task = ReviewTask(
            document_id=docs[i % len(docs)].id,
            rule_group_id=groups[i % len(groups)].id,
            status=TaskStatus.COMPLETED.value,
            owner_id=owner_id,
            progress=100
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        task_ids.append(task.id)

        # Create Results
        for j in range(rules_per_task):
            res = ReviewResultItem(
                task_id=task.id,
                rule_id=rules[j].id,
                result_code=ResultCode.PASS.value,
                reasoning="Good"
            )
            session.add(res)
        
        # Create Comparison Results (Simulate overhead)
        comp_doc = ComparisonDocument(filename=f"comp_{i}.pdf", status="DONE", owner_id=owner_id)
        session.add(comp_doc)
        session.commit()
        session.refresh(comp_doc)
        
        comp_res = ComparisonResult(
            task_id=task.id,
            comparison_document_id=comp_doc.id,
            conflict_score=0.1
        )
        session.add(comp_res)

    session.commit()
    return owner_id, task_ids

def run_performance_test():
    engine = setup_db()
    
    with Session(engine) as session:
        print("Seeding data...")
        owner_id, task_ids = seed_data(session, num_tasks=50, rules_per_task=30)
        print(f"Seeded 50 tasks with 30 results each.")
        
        print("\n--- Testing get_reviews (List all tasks) ---")
        qc = QueryCounter(engine)
        start_time = time.time()
        with qc:
            results = ReviewService.get_reviews(session, owner_id)
        duration = time.time() - start_time
        print(f"Time: {duration:.4f}s")
        print(f"Queries: {qc.count}")
        print(f"Items retrieved: {len(results)}")
        print(f"Queries per item: {qc.count / len(results) if len(results) > 0 else 0:.2f}")

        print("\n--- Testing get_review_task (Single task details) ---")
        task_id = task_ids[0]
        start_time = time.time()
        with qc:
            task = ReviewService.get_review_task(session, task_id)
        duration = time.time() - start_time
        print(f"Time: {duration:.4f}s")
        print(f"Queries: {qc.count}")
        
        print("\n--- Testing get_review_results (Task results) ---")
        start_time = time.time()
        with qc:
            results = ReviewService.get_review_results(session, task_id)
        duration = time.time() - start_time
        print(f"Time: {duration:.4f}s")
        print(f"Queries: {qc.count}")
        print(f"Items retrieved: {len(results)}")
        print(f"Queries per item: {qc.count / len(results) if len(results) > 0 else 0:.2f}")

if __name__ == "__main__":
    run_performance_test()