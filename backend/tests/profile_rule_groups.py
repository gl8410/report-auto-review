import sys
import os
import time
from sqlalchemy import event
from sqlmodel import Session, create_engine, SQLModel, select
from sqlmodel.pool import StaticPool
import uuid

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.rule import RuleGroup, Rule, RuleGroupType
from backend.models.review import ReviewTask, ReviewResultItem, TaskStatus
from backend.models.comparison import ComparisonResult
from backend.api.v1.routers.rule import get_child_group_ids, delete_group_recursive, get_rule_groups

class QueryCounter:
    def __init__(self, engine):
        self.engine = engine
        self.count = 0

    def __enter__(self):
        self.count = 0
        event.listen(self.engine, "before_cursor_execute", self.callback)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        event.remove(self.engine, "before_cursor_execute", self.callback)

    def callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1

def setup_db():
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine

def seed_nested_groups(session: Session, depth=3, width=5, rules_per_group=5):
    """Creates a tree of groups."""
    print(f"Seeding tree: depth={depth}, width={width}, rules_per_group={rules_per_group}")
    
    owner_id = "test_user"
    root = RuleGroup(name="Root", owner_id=owner_id, type="private")
    session.add(root)
    session.commit()
    session.refresh(root)
    
    current_level = [root]
    all_groups = [root]
    
    for d in range(depth):
        next_level = []
        for parent in current_level:
            for w in range(width):
                child = RuleGroup(
                    name=f"Child_{d}_{w}_{str(uuid.uuid4())[:4]}", 
                    parent_id=parent.id,
                    owner_id=owner_id,
                    type="private"
                )
                session.add(child)
                next_level.append(child)
                all_groups.append(child)
        
        session.commit()
        for g in next_level: session.refresh(g)
        current_level = next_level

    # Add Rules and Tasks to all groups
    print(f"Created {len(all_groups)} groups.")
    
    rules = []
    tasks = []
    
    for group in all_groups:
        # Add Rules
        for i in range(rules_per_group):
            r = Rule(
                group_id=group.id, 
                clause_number=f"1.{i}", 
                content="test", 
                owner_id=owner_id
            )
            session.add(r)
            rules.append(r)
            
        # Add a Task linked to this group
        t = ReviewTask(
            document_id="doc_id",
            rule_group_id=group.id,
            owner_id=owner_id,
            status=TaskStatus.COMPLETED.value
        )
        session.add(t)
        tasks.append(t)
        
    session.commit()
    print(f"Created {len(rules)} rules and {len(tasks)} tasks.")
    
    # Add results to tasks
    for t in tasks:
        r = ReviewResultItem(task_id=t.id, rule_id=rules[0].id)
        session.add(r)
    session.commit()
    
    return root, len(all_groups)

def run_profile():
    engine = setup_db()
    
    with Session(engine) as session:
        root, total_groups = seed_nested_groups(session, depth=3, width=5, rules_per_group=2)
        
        # Test 1: get_child_group_ids (Used in Recursive Get Rules)
        print("\n--- Testing get_child_group_ids ---")
        qc = QueryCounter(engine)
        start = time.time()
        with qc:
            ids = get_child_group_ids(session, root.id)
        dur = time.time() - start
        print(f"Time: {dur:.4f}s")
        print(f"Queries: {qc.count}")
        print(f"Found {len(ids)} descendants.")

        # Test 2: delete_group_recursive
        print("\n--- Testing delete_group_recursive ---")
        qc = QueryCounter(engine)
        start = time.time()
        with qc:
            # We pass session and the root group object
            # Note: We need to re-fetch root to ensure it's attached if needed, 
            # though here it's same session.
            delete_group_recursive(session, root)
            session.commit()
        dur = time.time() - start
        
        print(f"Time: {dur:.4f}s")
        print(f"Queries: {qc.count}")
        print(f"Estimated queries per group: {qc.count / total_groups:.2f}")

if __name__ == "__main__":
    run_profile()