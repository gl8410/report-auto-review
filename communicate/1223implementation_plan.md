# Professional Backend Reorganization Plan

This plan outlines the steps to reorganize the backend code into a professional, scalable structure with clear separation of concerns, versioned APIs, and domain-driven models.

## Proposed Structure

```
backend/
├── alembic/                # Database migrations
├── tests/                  # Automated tests
│   ├── unit/
│   └── integration/
├── backend/                # Source Code (Package)
│   ├── __init__.py
│   ├── main.py             # App initialization
│   ├── core/               # Global configs & Setup
│   │   ├── __init__.py
│   │   ├── config.py       # Pydantic Settings (Env vars)
│   │   ├── exceptions.py   # Custom exception handlers
│   │   ├── logging.py      # Centralized logging config
│   │   └── db.py           # DB Session/Engine (from database.py)
│   ├── models/             # SQLAlchemy models split by domain
│   │   ├── __init__.py     # Expose models
│   │   ├── base.py         # SQLAlchemy Base class
│   │   ├── rule.py
│   │   ├── document.py
│   │   ├── review.py
│   │   └── analysis.py
│   ├── schemas/            # Pydantic models
│   │   ├── __init__.py
│   │   ├── rule.py
│   │   ├── document.py
│   │   ├── review.py
│   │   └── analysis.py
│   ├── api/                # API Routes
│   │   ├── __init__.py
│   │   ├── deps.py         # Dependency Injection (get_db)
│   │   └── v1/             # Versioned API endpoints
│   │       ├── __init__.py
│   │       ├── rules.py
│   │       ├── documents.py
│   │       ├── reviews.py
│   │       ├── analysis.py
│   │       └── health.py
│   ├── services/           # Business Logic (Use cases)
│   │   ├── __init__.py
│   │   ├── review_service.py
│   │   ├── analysis_service.py
│   │   └── report_service.py
│   ├── integrations/       # External/Infrastructure services
│   │   ├── __init__.py
│   │   ├── llm_client.py   # LLM API interactions
│   │   └── vector_store.py # ChromaDB interactions
│   └── utils/              # Utility functions
│       ├── __init__.py
│       └── file_utils.py
├── .env                    # Environment variables
├── alembic.ini             # Migration config
└── requirements.txt
```

## Migration Strategy

> [!IMPORTANT]
> **Zero-Downtime Approach**: Keep current server running while building new structure alongside.

### Phase 1: Preparation (Safe)
- Create new directory structure without touching existing files
- Git commit after each major step for easy rollback
- Keep `uvicorn` running on current code during entire process

### Phase 2: Incremental Migration (Reversible)
- Build new modules while old ones still work
- Update imports gradually, test after each module
- Use relative imports within `backend/` package

### Phase 3: Cutover (Final)
- Update `uvicorn` command to use new entry point
- Archive old files as `_old/` instead of deleting

## Detailed Implementation Steps

### Step 1: Create Directory Structure (5 min)
```bash
# Create new package structure
mkdir -p backend/backend/{core,models,schemas,api/v1,services,integrations,utils}
mkdir -p backend/tests/{unit,integration}
mkdir -p backend/alembic

# Create all __init__.py files
touch backend/backend/__init__.py
touch backend/backend/{core,models,schemas,api,api/v1,services,integrations,utils}/__init__.py
```

### Step 2: Setup Core Infrastructure (15 min)

**2.1 Create `backend/backend/core/config.py`**
- Extract all `os.getenv()` calls from current codebase
- Create Pydantic Settings class with all environment variables
- Add validation and defaults

**2.2 Create `backend/backend/core/db.py`**
- Copy content from `database.py`
- Update imports to use new config
- Keep old `database.py` temporarily for compatibility

**2.3 Create `backend/backend/core/exceptions.py`**
- Define custom exceptions (e.g., `DocumentNotFoundError`)

**2.4 Create `backend/backend/core/logging.py`**
- Centralized logging configuration

### Step 3: Refactor Models (20 min)

**3.1 Create `backend/backend/models/base.py`**
```python
from sqlmodel import SQLModel

# This will be imported by all model files
```

**3.2 Split models into domain files:**
- `models/rule.py`: `RuleGroup`, `Rule`
- `models/document.py`: `Document`, `DocumentStatus`
- `models/review.py`: `ReviewTask`, `ReviewResultItem`, `TaskStatus`
- `models/analysis.py`: Content from `models_analysis.py`

**3.3 Update `models/__init__.py`**
```python
from .rule import RuleGroup, Rule
from .document import Document, DocumentStatus
from .review import ReviewTask, ReviewResultItem, TaskStatus
from .analysis import HistoryAnalysisTask, InferredOpinion, AnalysisStatus
```

### Step 4: Create Schemas (15 min)

**4.1 Move schemas from `main.py`:**
- `schemas/rule.py`: `RuleGroupCreate`, `RuleGroupResponse`, `RuleCreate`, `RuleResponse`, `RuleUpdate`
- `schemas/document.py`: Document-related schemas
- `schemas/review.py`: `ReviewStartRequest`, `ReviewResultResponse`
- `schemas/analysis.py`: Analysis-related schemas

### Step 5: Setup Integrations Layer (25 min)

**5.1 Create `integrations/llm_client.py`**
- Move from `services.py`:
  - `call_llm()`
  - `health_check_llm()`
  - `parse_rules_from_text()`
  - All LLM-related constants and schemas

**5.2 Create `integrations/vector_store.py`**
- Move from `services.py`:
  - `get_chroma_client()`
  - `get_embeddings()`
  - `ingest_document_to_chroma()`
  - `delete_document_from_chroma()`
  - `search_document_chunks()`

### Step 6: Implement Services Layer (30 min)

**6.1 Create `services/document_service.py`**
- `extract_text_from_file()`
- `split_into_sentences()`
- `dynamic_chunk_text()`
- `process_document_background()`

**6.2 Create `services/review_service.py`**
- `generate_review_queries()`
- `compare_rule_with_context()`
- `execute_review_for_rule()`
- `execute_review_background()`

**6.3 Create `services/analysis_service.py`**
- `compare_documents_and_extract_opinions()`

**6.4 Create `services/report_service.py`**
- `generate_summary_report_content()`

### Step 7: Build API Layer (30 min)

**7.1 Create `api/deps.py`**
```python
from backend.core.db import get_session

def get_db():
    return get_session()
```

**7.2 Create API routers in `api/v1/`:**
- `health.py`: Health check endpoint
- `rules.py`: All `/rule-groups` and `/rules` endpoints
- `documents.py`: All `/documents` endpoints
- `reviews.py`: All `/reviews` endpoints
- `analysis.py`: History analysis endpoints

**7.3 Create `api/v1/__init__.py`**
```python
from fastapi import APIRouter
from . import health, rules, documents, reviews, analysis

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(rules.router, prefix="/rule-groups", tags=["rules"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(analysis.router, prefix="/history-analysis", tags=["analysis"])
```

### Step 8: Update Main Application (10 min)

**8.1 Create new `backend/backend/main.py`**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.db import init_db
from backend.api.v1 import api_router

app = FastAPI(title="ADS System API", version="2.0.0")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
app.include_router(api_router, prefix="/api/v1")
```

**8.2 Update run command:**
- Change from: `uvicorn main:app --reload`
- To: `uvicorn backend.main:app --reload`

### Step 9: Setup Alembic (10 min)

```bash
cd backend
alembic init alembic
```

**9.1 Update `alembic/env.py`:**
- Point to new models location
- Import all models for autogenerate

**9.2 Create initial migration from existing DB:**
```bash
alembic revision --autogenerate -m "initial schema"
```

### Step 10: Reorganize Tests (15 min)

- Move unit tests to `tests/unit/`
- Update imports to use new package structure
- Run tests to verify: `pytest`

### Step 11: Final Cleanup (5 min)

- Move old files to `backend/_old/` directory
- Delete `models_analysis.py`, old `database.py`, old `services.py`, old `main.py`
- Update `.gitignore` if needed

## Import Update Strategy

**Before (old imports):**
```python
from database import get_session
from models import Rule, Document
from services import call_llm, execute_review_for_rule
```

**After (new imports):**
```python
from backend.core.db import get_session
from backend.models import Rule, Document
from backend.integrations.llm_client import call_llm
from backend.services.review_service import execute_review_for_rule
```

**Systematic approach:**
1. Use IDE's "Find in Files" for each old import
2. Update progressively: first models, then services, then API
3. Test after each module conversion

## Rollback Plan

**If issues occur:**
1. Keep old `_old/` directory with original files
2. Each step is in git - can revert with `git reset --hard <commit>`
3. Change uvicorn command back to old entry point
4. No data loss - database unchanged during structure refactor

## Verification Plan

### Automated Tests
```bash
cd backend
pytest tests/ -v
```

### Manual Verification Checklist
- [ ] Server starts: `uvicorn backend.main:app --reload`
- [ ] API docs accessible: `http://localhost:8000/docs`
- [ ] Health check: GET `/api/v1/health`
- [ ] Create rule group, add rules
- [ ] Upload document, verify indexing
- [ ] Start review task, check progress
- [ ] Export rules to CSV
- [ ] Generate summary report

### 3. Split `services.py`
- Distribute functions from `services.py` into the new `backend/services/` modules.
- **llm_service.py**: `call_llm`, `health_check_llm`, `parse_rules_from_text`.
- **vector_service.py**: `get_chroma_client`, `get_embeddings`, `ingest_document_to_chroma`, `delete_document_from_chroma`, `search_document_chunks`.
- **document_service.py**: `extract_text_from_file`, `split_into_sentences`, `dynamic_chunk_text`, `process_document_background`.
- **review_service.py**: `generate_review_queries`, `compare_rule_with_context`, `execute_review_for_rule`, `execute_review_background`.
- **analysis_service.py**: `compare_documents_and_extract_opinions`.
- **report_service.py**: `generate_summary_report_content`.

### 4. Split `main.py` into API Routes
- Move endpoint logic from `main.py` to `backend/api/` using `APIRouter`.
- Update `main.py` to include these routers.

### 5. Utilities
- Move CSV import/export logic to `backend/utils/file_utils.py`.

## Verification Plan

### Automated Tests
- Run existing tests in `backend/tests/` to ensure no regressions.
- Verify that the FastAPI app starts correctly with `uvicorn main:app`.

### Manual Verification
- Test key endpoints using a tool like Postman or the frontend:
    - Health check
    - Rule group creation and rule listing
    - Document upload and indexing status
    - Starting a review task and checking progress
    - Exporting rules to CSV
