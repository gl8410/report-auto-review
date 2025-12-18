
import sys
import os
from sqlmodel import Session, select

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import engine, init_db
from models import RuleGroup, ReviewTask, ReviewResultItem, Rule

def cleanup_all_rules():
    init_db()
    with Session(engine) as session:
        print("Starting cleanup of all Rule Groups...")
        
        # Get all groups
        groups = session.exec(select(RuleGroup)).all()
        print(f"Found {len(groups)} rule groups.")
        
        for group in groups:
            print(f"Deleting group: {group.name} ({group.id})")
            
            # 1. Delete associated Review Tasks and Results
            tasks = session.exec(select(ReviewTask).where(ReviewTask.rule_group_id == group.id)).all()
            for task in tasks:
                # Delete results
                results = session.exec(select(ReviewResultItem).where(ReviewResultItem.task_id == task.id)).all()
                for res in results:
                    session.delete(res)
                # Delete task
                session.delete(task)
            
            # 2. Delete rules
            rules = session.exec(select(Rule).where(Rule.group_id == group.id)).all()
            for rule in rules:
                session.delete(rule)
            
            # 3. Delete group
            session.delete(group)
            
        session.commit()
        print("Cleanup completed successfully.")

if __name__ == "__main__":
    cleanup_all_rules()
