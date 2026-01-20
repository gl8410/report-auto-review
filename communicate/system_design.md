# Auto-Review & Decision Support System (ADS) - System Design Specification

## 1. Introduction
This document outlines the detailed system design for the Automated Document Review System (ADS). The system allows users to define regulatory rule groups, upload technical documents (PDF/DOCX), and automatically review these documents against the rules using LLM-based analysis.

## 2. System Architecture

### 2.1 High-Level Architecture
The system follows a standard 3-tier architecture:
- **Presentation Layer (Frontend):** React + Vite SPA.
- **Application Layer (Backend):** FastAPI (Python) interacting with AI services.
- **Data Layer:** PostgreSQL (Relational Data), ChromaDB (Vector Data), Local File System (Document Storage).

### 2.2 Tech Stack
- **Frontend:** React 19, TypeScript, Tailwind CSS, Lucide Icons, Vite.
- **Backend:** Python 3.12, FastAPI, AsyncIO.
- **Database:** PostgreSQL (SQLModel/SQLAlchemy).
- **Vector Search:** ChromaDB for RAG (Retrieval-Augmented Generation).
- **AI/LLM:** OpenAI-compatible API (Integration via LangChain/Direct HTTP).
- **PDF Processing:** MinerU / OmniParse (for high-fidelity parsing).

## 3. Database Design

The database uses PostgreSQL for structured data. The schema is defined using SQLModel.

### 3.1 Entity Relationship Diagram (Description)

*   **RuleGroup** (One) ----< **Rule** (Many)
*   **Document** (One) ----< **ReviewTask** (Many)
*   **ReviewTask** (One) ----< **ReviewResultItem** (Many)
*   **Rule** (One) ----< **ReviewResultItem** (Many)

### 3.2 Key Tables

#### `rule_groups`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Unique identifier |
| `name` | String | Not Null | Name of the regulation/standard |
| `description` | String | | Optional description |
| `created_at` | DateTime | | Timestamp |

#### `rules`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Unique identifier |
| `group_id` | UUID | FK -> `rule_groups.id` | Parent group |
| `clause` | String | | Clause number (e.g., "3.1.2") |
| `content` | Text | Not Null | The actual rule text |
| `description` | Text | | Rule interpretation or details |
| `rule_type` | Enum | | `mandatory`, `recommended`, etc. |

#### `documents`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Unique identifier |
| `filename` | String | Not Null | Original filename |
| `storage_path`| String | Not Null | Path on disk |
| `status` | Enum | | `uploaded`, `parsing`, `indexed`, `failed` |
| `meta_info` | JSON | | Extracted metadata (author, date) |

#### `review_tasks`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Unique identifier |
| `document_id` | UUID | FK -> `documents.id` | Subject document |
| `rule_group_id`| UUID | FK -> `rule_groups.id` | Applied standard |
| `status` | Enum | | `pending`, `processing`, `completed`, `failed` |
| `progress` | Float | | 0.0 to 100.0 |

#### `review_results`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Unique identifier |
| `task_id` | UUID | FK -> `review_tasks.id` | Parent task |
| `rule_id` | UUID | FK -> `rules.id` | Specific rule checked |
| `result` | Enum | | `pass`, `fail`, `not_applicable`, `manual_check` |
| `reasoning` | Text | | LLM explanation |
| `evidence` | Text | | Quoted text from document |
| `page_num` | Integer| | Page reference |

## 4. API Interface Design (REST)

All API responses follow a standard wrapper `{"data": ..., "message": ..., "status": ...}` where applicable, or direct Pydantic model updates.

### 4.1 Rules Management
- `POST /api/v1/rule-groups`: Create a new rule group.
- `GET /api/v1/rule-groups`: List all rule groups.
- `POST /api/v1/rule-groups/{id}/upload`: Upload a standard (.txt/.md) for parsing.
- `GET /api/v1/rule-groups/{id}/rules`: Get all rules in a group.
- `PATCH /api/v1/rules/{id}`: Update specific rule details.

### 4.2 Document Management
- `POST /api/v1/documents/upload`: Upload file (multipart/form-data).
    - *Trigger:* Starts background task for Parsing -> Chunking -> Vectorizing.
- `GET /api/v1/documents`: List uploaded documents and status.
- `GET /api/v1/documents/{id}/status`: Poll specific document processing status.

### 4.3 Review Execution
- `POST /api/v1/reviews`: Start a new review.
    - *Body:* `{ "document_id": "uuid", "rule_group_id": "uuid" }`
- `GET /api/v1/reviews/{id}`: Get task status and summary stats.
- `GET /api/v1/reviews/{id}/results`: Get detailed line-by-line review results.
- `POST /api/v1/reviews/{id}/report`: Generate PDF report for download.

### 4.4 History Analysis
- `POST /api/v1/history-analysis/compare`: Compare multiple documents for trends.

## 5. Core Business Logic & Data Flow

### 5.1 Document Ingestion Pipeline
1.  **Upload:** User uploads PDF. File saved to `backend/uploads/`.
2.  **Parsing:** `DocumentService` calls parsing utility (e.g., MinerU/OmniParse) to convert PDF to Markdown.
3.  **Chunking:** Text is split into semantic chunks (sliding window or header-based).
4.  **Embedding:** Chunks are passed to Embedding Model (e.g., BGE-M3 or OpenAI).
5.  **Storage:** Embeddings + Metadata stored in ChromaDB collection named after `document_id`.

### 5.2 Review Intelligence Pipeline
This is the "Dual-Source" review process:
1.  **Fetch Rule:** System iterates through active rules in the selected `RuleGroup`.
2.  **Retrieval (RAG):**
    - Convert Rule Content into a search query.
    - Query ChromaDB for top $k$ relevant chunks from the Document.
3.  **LLM Verification:**
    - Construct Prompt:
        ```text
        Standard: {rule_content}
        Context: {retrieved_chunks}
        Task: Determine if the context complies with the standard.
        Output: JSON { result: 'pass'|'fail', reasoning: '...', evidence: '...' }
        ```
    - Call LLM API.
4.  **Aggregation:** Parse response and save to `ReviewResultItem`.
5.  **Completion:** Update `ReviewTask` status to `completed`.

## 6. Frontend Design

### 6.1 Key Components
- **Layout:** Sidebar navigation (Rules, Documents, Reviews, History).
- **DocumentViewer:** Integrated PDF viewer with highlight capabilities (for "Evidence" linking).
- **StatusBadge:** Reusable component for color-coded statuses (Processing, Success, Fail).
- **ReviewTable:** Interactive table for review results with expand/collapse rows for detailed reasoning.

### 6.2 State Management
- Use React Context or basic Hooks for local state.
- Polling mechanism (interval hooks) for status updates on Documents and Reviews.

## 7. Security & Performance

### 7.1 Security
- **Environment Variables:** All API Keys (OpenAI, DB Params) stored in `.env`.
- **Input Validation:** Pydantic models validate all incoming requests.
- **CORS:** configuration restricted to frontend origins.

### 7.2 Performance
- **AsyncIO:** Leveraging FastAPI's async nature for non-blocking LLM/DB calls.
- **Background Tasks:** Heavy lifting (Ingestion, Review loops) runs in background threads/processes to keep API responsive.
- **Vector Search:** HNSW indexing in ChromaDB for sub-second retrieval.