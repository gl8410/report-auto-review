
import sys
import os
from sqlmodel import SQLModel

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import engine, init_db
# Import models to ensure they are registered with SQLModel.metadata
from models import RuleGroup, Rule, Document, ReviewTask, ReviewResultItem

def reset_database():
    print("Resetting database...")
    print("Dropping all tables...")
    SQLModel.metadata.drop_all(engine)
    print("Creating all tables...")
    init_db()
    print("Database reset complete.")

if __name__ == "__main__":
    reset_database()
