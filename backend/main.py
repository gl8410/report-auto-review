"""
FastAPI Main Application for ADS System.
Provides REST API endpoints for Rule Management, Document Management, and Review.
"""
import os
import io
import csv
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from pydantic import BaseModel

from database import init_db, get_session, engine
from models import RuleGroup, Rule, Document, ReviewTask, ReviewResultItem, DocumentStatus, TaskStatus
from services import (
    parse_rules_from_text, health_check_llm, extract_text_from_file,
    ingest_document_to_chroma, delete_document_from_chroma
)

# Uploads directory
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Valid review types
VALID_REVIEW_TYPES = ["内容完整性", "计算结果准确性", "禁止条款", "前后逻辑一致性", "措施遵从性", "计算正确性"]
# Valid importance levels
VALID_IMPORTANCE = ["一般", "中等", "重要"]


# ============== Pydantic Request/Response Schemas ==============

class RuleGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RuleGroupResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: datetime


class RuleCreate(BaseModel):
    clause_number: str
    content: str
    standard_name: Optional[str] = None
    review_type: Optional[str] = None
    importance: str = "中等"


class RuleResponse(BaseModel):
    id: str
    group_id: str
    clause_number: str
    content: str
    standard_name: Optional[str]
    review_type: Optional[str]
    importance: str


class RuleUpdate(BaseModel):
    clause_number: Optional[str] = None
    content: Optional[str] = None
    standard_name: Optional[str] = None
    review_type: Optional[str] = None
    importance: Optional[str] = None


# ============== Application Lifespan ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


# ============== FastAPI App ==============

app = FastAPI(
    title="ADS System API",
    description="AI Document Review System - Rule Management & Review API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Health Check ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    llm_ok = await health_check_llm()
    return {
        "status": "ok",
        "llm_available": llm_ok,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============== Rule Group Endpoints ==============

@app.get("/rule-groups", response_model=List[RuleGroupResponse])
def get_rule_groups(session: Session = Depends(get_session)):
    """Get all rule groups."""
    groups = session.exec(select(RuleGroup).order_by(RuleGroup.created_at.desc())).all()
    return groups


@app.post("/rule-groups", response_model=RuleGroupResponse)
def create_rule_group(data: RuleGroupCreate, session: Session = Depends(get_session)):
    """Create a new rule group."""
    group = RuleGroup(
        name=data.name,
        description=data.description
    )
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


@app.get("/rule-groups/{group_id}", response_model=RuleGroupResponse)
def get_rule_group(group_id: str, session: Session = Depends(get_session)):
    """Get a specific rule group."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")
    return group


@app.put("/rule-groups/{group_id}", response_model=RuleGroupResponse)
def update_rule_group(group_id: str, data: RuleGroupCreate, session: Session = Depends(get_session)):
    """Update a rule group."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")
    group.name = data.name
    if data.description is not None:
        group.description = data.description
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


@app.delete("/rule-groups/{group_id}")
def delete_rule_group(group_id: str, session: Session = Depends(get_session)):
    """Delete a rule group and all its rules."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")
    # Delete all rules in this group first
    rules = session.exec(select(Rule).where(Rule.group_id == group_id)).all()
    for rule in rules:
        session.delete(rule)
    session.delete(group)
    session.commit()
    return {"message": "Rule group deleted"}


# ============== Rule Endpoints ==============

@app.get("/rule-groups/{group_id}/rules", response_model=List[RuleResponse])
def get_rules(group_id: str, session: Session = Depends(get_session)):
    """Get all rules in a group."""
    rules = session.exec(select(Rule).where(Rule.group_id == group_id)).all()
    return rules


@app.post("/rule-groups/{group_id}/rules", response_model=RuleResponse)
def create_rule(group_id: str, data: RuleCreate, session: Session = Depends(get_session)):
    """Create a new rule in a group."""
    # Verify group exists
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    # Validate review_type and importance
    if data.review_type and data.review_type not in VALID_REVIEW_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid review_type. Must be one of: {VALID_REVIEW_TYPES}")
    if data.importance not in VALID_IMPORTANCE:
        raise HTTPException(status_code=400, detail=f"Invalid importance. Must be one of: {VALID_IMPORTANCE}")

    rule = Rule(
        group_id=group_id,
        clause_number=data.clause_number,
        content=data.content,
        standard_name=data.standard_name,
        review_type=data.review_type,
        importance=data.importance
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@app.put("/rules/{rule_id}", response_model=RuleResponse)
def update_rule(rule_id: str, data: RuleUpdate, session: Session = Depends(get_session)):
    """Update a rule."""
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if data.clause_number is not None:
        rule.clause_number = data.clause_number
    if data.content is not None:
        rule.content = data.content
    if data.standard_name is not None:
        rule.standard_name = data.standard_name
    if data.review_type is not None:
        if data.review_type not in VALID_REVIEW_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid review_type. Must be one of: {VALID_REVIEW_TYPES}")
        rule.review_type = data.review_type
    if data.importance is not None:
        if data.importance not in VALID_IMPORTANCE:
            raise HTTPException(status_code=400, detail=f"Invalid importance. Must be one of: {VALID_IMPORTANCE}")
        rule.importance = data.importance

    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@app.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, session: Session = Depends(get_session)):
    """Delete a rule."""
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
    return {"message": "Rule deleted"}


# ============== File Upload & LLM Parsing ==============

async def process_uploaded_rules(group_id: str, content: str, filename: str, session: Session) -> int:
    """Background task to parse rules from uploaded file using LLM.

    Returns:
        Number of rules successfully parsed and added
    """
    try:
        parsed = await parse_rules_from_text(content, filename)

        if not parsed.rules:
            raise ValueError("未能从文件中解析出任何规则")

        # Create rules from parsed data
        for parsed_rule in parsed.rules:
            rule = Rule(
                group_id=group_id,
                clause_number=parsed_rule.clause_number,
                content=parsed_rule.content,
                standard_name=parsed.standard_name,
                review_type=parsed_rule.review_type,
                importance=parsed_rule.importance
            )
            session.add(rule)
        session.commit()
        print(f"Successfully parsed {len(parsed.rules)} rules from {filename}")
        return len(parsed.rules)
    except Exception as e:
        print(f"Error processing rules: {e}")
        raise


@app.post("/rule-groups/{group_id}/upload")
async def upload_rules_file(
    group_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session)
):
    """Upload a file (txt, md, pdf, docx) and parse rules using LLM."""
    # Verify group exists
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    filename = file.filename or "unknown"

    # Check file type
    allowed_extensions = ('.txt', '.md', '.pdf', '.docx')
    if not filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are supported")

    # Read file content
    content = await file.read()

    try:
        # Extract text based on file type
        text_content = await extract_text_from_file(content, filename)

        # Process rules with LLM
        rules_count = await process_uploaded_rules(group_id, text_content, filename, session)

        return {"message": f"成功从 '{filename}' 解析并导入 {rules_count} 条规则", "group_id": group_id, "rules_count": rules_count}
    except Exception as e:
        error_msg = str(e)
        print(f"Error uploading rules: {error_msg}")
        raise HTTPException(status_code=500, detail=f"处理文件失败: {error_msg}")


# ============== CSV Import/Export ==============

@app.get("/rule-groups/{group_id}/export-csv")
def export_rules_csv(group_id: str, session: Session = Depends(get_session)):
    """Export all rules in a group as CSV file."""
    from urllib.parse import quote

    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    rules = session.exec(select(Rule).where(Rule.group_id == group_id)).all()

    # Create CSV in memory with UTF-8 BOM for Excel compatibility
    output = io.StringIO()
    # Add BOM for Excel to recognize UTF-8
    output.write('\ufeff')
    writer = csv.writer(output)

    # Write header
    writer.writerow(["id", "standard_name", "clause_number", "content", "review_type", "importance"])

    # Write rules
    for rule in rules:
        writer.writerow([
            rule.id,
            rule.standard_name or "",
            rule.clause_number,
            rule.content,
            rule.review_type or "",
            rule.importance
        ])

    output.seek(0)

    # URL-encode the filename for non-ASCII characters (RFC 5987)
    filename = f"{group.name}_rules.csv"
    encoded_filename = quote(filename, safe='')

    # Use both filename (ASCII fallback) and filename* (UTF-8 encoded) for compatibility
    content_disposition = f"attachment; filename=\"rules.csv\"; filename*=UTF-8''{encoded_filename}"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": content_disposition
        }
    )


@app.post("/rule-groups/{group_id}/import-csv")
async def import_rules_csv(
    group_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """Import rules from CSV file."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    filename = file.filename or "unknown.csv"
    if not filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    try:
        text_content = content.decode('utf-8')
    except UnicodeDecodeError:
        text_content = content.decode('gbk', errors='ignore')

    # Parse CSV
    reader = csv.DictReader(io.StringIO(text_content))
    imported_count = 0

    for row in reader:
        # Validate required fields
        clause_number = row.get('clause_number', '').strip()
        content_text = row.get('content', '').strip()

        if not clause_number or not content_text:
            continue  # Skip invalid rows

        # Get optional fields with defaults
        standard_name = row.get('standard_name', '').strip() or None
        review_type = row.get('review_type', '').strip() or None
        importance = row.get('importance', '中等').strip()

        # Validate review_type and importance
        if review_type and review_type not in VALID_REVIEW_TYPES:
            review_type = None
        if importance not in VALID_IMPORTANCE:
            importance = "中等"

        rule = Rule(
            group_id=group_id,
            standard_name=standard_name,
            clause_number=clause_number,
            content=content_text,
            review_type=review_type,
            importance=importance
        )
        session.add(rule)
        imported_count += 1

    session.commit()

    return {"message": f"Imported {imported_count} rules from CSV", "group_id": group_id}


# ============== Document Endpoints ==============

@app.get("/documents")
def get_documents(session: Session = Depends(get_session)):
    """Get all documents ordered by upload time (newest first)."""
    docs = session.exec(select(Document).order_by(Document.upload_time.desc())).all()
    return docs


@app.get("/documents/{doc_id}")
def get_document(doc_id: str, session: Session = Depends(get_session)):
    """Get a specific document."""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def process_document_background(doc_id: str, file_content: bytes, filename: str):
    """Background task to parse and vectorize document."""
    from sqlmodel import Session as SyncSession

    with SyncSession(engine) as session:
        doc = session.get(Document, doc_id)
        if not doc:
            print(f"Document {doc_id} not found for processing")
            return

        try:
            # Update status to PARSING
            doc.status = DocumentStatus.PARSING.value
            session.add(doc)
            session.commit()

            # Extract text from document
            text_content = await extract_text_from_file(file_content, filename)

            if not text_content or len(text_content.strip()) < 10:
                raise ValueError("Document contains no extractable text")

            # Store text in meta_info for reference
            import json
            doc.meta_info = json.dumps({
                "text_length": len(text_content),
                "filename": filename
            })
            session.add(doc)
            session.commit()

            # Ingest to ChromaDB
            chunk_count = await ingest_document_to_chroma(doc_id, text_content, filename)

            # Update status to INDEXED
            doc.status = DocumentStatus.INDEXED.value
            doc.meta_info = json.dumps({
                "text_length": len(text_content),
                "chunk_count": chunk_count,
                "filename": filename
            })
            session.add(doc)
            session.commit()

            print(f"Successfully indexed document {filename} with {chunk_count} chunks")

        except Exception as e:
            print(f"Error processing document {filename}: {e}")
            doc.status = DocumentStatus.FAILED.value
            import json
            doc.meta_info = json.dumps({"error": str(e)})
            session.add(doc)
            session.commit()


@app.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session)
):
    """Upload a document for review (supports .pdf, .docx, .doc)."""
    filename = file.filename or "unknown"

    # Validate file type
    valid_extensions = ['.pdf', '.docx', '.doc']
    ext = os.path.splitext(filename)[1].lower()
    if ext not in valid_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(valid_extensions)}"
        )

    # Read file content
    file_content = await file.read()

    # Generate unique filename for storage
    doc_id = str(uuid.uuid4())
    storage_filename = f"{doc_id}{ext}"
    storage_path = os.path.join(UPLOADS_DIR, storage_filename)

    # Save file to disk
    with open(storage_path, 'wb') as f:
        f.write(file_content)

    # Create document record
    doc = Document(
        id=doc_id,
        filename=filename,
        storage_path=storage_path,
        status=DocumentStatus.UPLOADED.value
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    # Start background processing
    background_tasks.add_task(process_document_background, doc_id, file_content, filename)

    return doc


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, session: Session = Depends(get_session)):
    """Delete a document and its vectors from ChromaDB."""
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from ChromaDB
    await delete_document_from_chroma(doc_id)

    # Delete file from disk
    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except Exception as e:
            print(f"Warning: Could not delete file {doc.storage_path}: {e}")

    # Delete from database
    session.delete(doc)
    session.commit()

    return {"message": f"Document '{doc.filename}' deleted successfully"}


# ============== Review Endpoints ==============

class ReviewStartRequest(BaseModel):
    document_id: str
    rule_group_id: str


class ReviewResultResponse(BaseModel):
    id: str
    task_id: str
    rule_id: str
    clause_number: str
    rule_content: str
    result_code: str
    reasoning: Optional[str]
    evidence: Optional[str]
    suggestion: Optional[str]


async def execute_review_background(task_id: str, document_id: str, rule_group_id: str):
    """Background task to execute the review process with progress updates."""
    from sqlmodel import Session as SyncSession
    from services import execute_review_for_rule

    with SyncSession(engine) as session:
        # Get task
        task = session.get(ReviewTask, task_id)
        if not task:
            print(f"Task {task_id} not found")
            return

        # Get document
        doc = session.get(Document, document_id)
        if not doc:
            task.status = TaskStatus.FAILED.value
            session.commit()
            return

        # Get rules
        rules = session.exec(select(Rule).where(Rule.group_id == rule_group_id)).all()
        if not rules:
            task.status = TaskStatus.FAILED.value
            session.commit()
            return

        # Update task to PROCESSING
        task.status = TaskStatus.PROCESSING.value
        task.start_time = datetime.now(timezone.utc)
        session.commit()

        total_rules = len(rules)
        completed = 0

        print(f"[Review {task_id}] Starting review of {total_rules} rules against document '{doc.filename}'")

        for i, rule in enumerate(rules):
            try:
                print(f"[Review {task_id}] Processing rule {i+1}/{total_rules}: {rule.clause_number}")

                # Execute review for this rule
                rule_dict = {
                    "id": rule.id,
                    "content": rule.content,
                    "clause_number": rule.clause_number,
                    "review_type": rule.review_type,
                    "importance": rule.importance
                }

                result = await execute_review_for_rule(
                    rule=rule_dict,
                    document_id=document_id,
                    document_filename=doc.filename
                )

                # Save result
                result_item = ReviewResultItem(
                    task_id=task_id,
                    rule_id=rule.id,
                    result_code=result["result_code"],
                    reasoning=result["reasoning"],
                    evidence=result["evidence"],
                    suggestion=result["suggestion"]
                )
                session.add(result_item)

                # Update progress
                completed += 1
                task.progress = int((completed / total_rules) * 100)
                session.commit()

                print(f"[Review {task_id}] Rule {rule.clause_number}: {result['result_code']}")

            except Exception as e:
                print(f"[Review {task_id}] Error processing rule {rule.clause_number}: {e}")
                # Save error result
                result_item = ReviewResultItem(
                    task_id=task_id,
                    rule_id=rule.id,
                    result_code="MANUAL_CHECK",
                    reasoning=f"处理出错: {str(e)}",
                    evidence="",
                    suggestion="请人工审查"
                )
                session.add(result_item)
                completed += 1
                task.progress = int((completed / total_rules) * 100)
                session.commit()

        # Mark task as completed
        task.status = TaskStatus.COMPLETED.value
        task.progress = 100
        task.end_time = datetime.now(timezone.utc)
        session.commit()

        print(f"[Review {task_id}] Review completed! {completed} rules processed.")


@app.get("/reviews")
def get_reviews(session: Session = Depends(get_session)):
    """Get all review tasks with document and rule group info."""
    tasks = session.exec(
        select(ReviewTask).order_by(ReviewTask.created_at.desc())
    ).all()

    # Enrich with document and rule group names
    enriched = []
    for task in tasks:
        doc = session.get(Document, task.document_id)
        group = session.get(RuleGroup, task.rule_group_id)
        enriched.append({
            "id": task.id,
            "document_id": task.document_id,
            "document_name": doc.filename if doc else "Unknown",
            "rule_group_id": task.rule_group_id,
            "rule_group_name": group.name if group else "Unknown",
            "status": task.status,
            "progress": task.progress,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "end_time": task.end_time.isoformat() if task.end_time else None,
            "created_at": task.created_at.isoformat()
        })

    return enriched


@app.post("/reviews/start")
async def start_review(
    data: ReviewStartRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Start a new review task."""
    # Validate document exists and is indexed
    doc = session.get(Document, data.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != DocumentStatus.INDEXED.value:
        raise HTTPException(status_code=400, detail=f"Document is not indexed yet. Current status: {doc.status}")

    # Validate rule group exists and has rules
    group = session.get(RuleGroup, data.rule_group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    rules = session.exec(select(Rule).where(Rule.group_id == data.rule_group_id)).all()
    if not rules:
        raise HTTPException(status_code=400, detail="Rule group has no rules")

    # Create task
    task = ReviewTask(
        document_id=data.document_id,
        rule_group_id=data.rule_group_id,
        status=TaskStatus.PENDING.value,
        progress=0
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    # Start background execution
    background_tasks.add_task(
        execute_review_background,
        task.id,
        data.document_id,
        data.rule_group_id
    )

    return {
        "task_id": task.id,
        "status": task.status,
        "message": f"Review started for document '{doc.filename}' with {len(rules)} rules",
        "total_rules": len(rules)
    }


@app.get("/reviews/{task_id}")
def get_review_task(task_id: str, session: Session = Depends(get_session)):
    """Get review task status with details."""
    task = session.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    doc = session.get(Document, task.document_id)
    group = session.get(RuleGroup, task.rule_group_id)

    # Count results by type
    results = session.exec(
        select(ReviewResultItem).where(ReviewResultItem.task_id == task_id)
    ).all()

    stats = {"PASS": 0, "REJECT": 0, "MANUAL_CHECK": 0}
    for r in results:
        if r.result_code in stats:
            stats[r.result_code] += 1

    return {
        "id": task.id,
        "document_id": task.document_id,
        "document_name": doc.filename if doc else "Unknown",
        "rule_group_id": task.rule_group_id,
        "rule_group_name": group.name if group else "Unknown",
        "status": task.status,
        "progress": task.progress,
        "start_time": task.start_time.isoformat() if task.start_time else None,
        "end_time": task.end_time.isoformat() if task.end_time else None,
        "created_at": task.created_at.isoformat(),
        "results_count": len(results),
        "stats": stats
    }


@app.get("/reviews/{task_id}/results")
def get_review_results(task_id: str, session: Session = Depends(get_session)):
    """Get review results for a task with rule details."""
    task = session.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    results = session.exec(
        select(ReviewResultItem).where(ReviewResultItem.task_id == task_id)
    ).all()

    # Enrich with rule info
    enriched = []
    for result in results:
        rule = session.get(Rule, result.rule_id)
        enriched.append({
            "id": result.id,
            "task_id": result.task_id,
            "rule_id": result.rule_id,
            "clause_number": rule.clause_number if rule else "N/A",
            "standard_name": rule.standard_name if rule else "N/A",
            "rule_content": rule.content if rule else "N/A",
            "review_type": rule.review_type if rule else None,
            "importance": rule.importance if rule else "中等",
            "result_code": result.result_code,
            "reasoning": result.reasoning,
            "evidence": result.evidence,
            "suggestion": result.suggestion,
            "created_at": result.created_at.isoformat()
        })

    return enriched


@app.delete("/reviews/{task_id}")
def delete_review_task(task_id: str, session: Session = Depends(get_session)):
    """Delete a review task and its results."""
    task = session.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Delete results first
    results = session.exec(
        select(ReviewResultItem).where(ReviewResultItem.task_id == task_id)
    ).all()
    for result in results:
        session.delete(result)

    # Delete task
    session.delete(task)
    session.commit()

    return {"message": f"Review task and {len(results)} results deleted"}


# ============== Review Result Item CRUD ==============

class ResultUpdateRequest(BaseModel):
    result_code: Optional[str] = None
    reasoning: Optional[str] = None
    evidence: Optional[str] = None
    suggestion: Optional[str] = None


@app.get("/results/{result_id}")
def get_review_result(result_id: str, session: Session = Depends(get_session)):
    """Get a single review result item with rule details."""
    result = session.get(ReviewResultItem, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    rule = session.get(Rule, result.rule_id)
    return {
        "id": result.id,
        "task_id": result.task_id,
        "rule_id": result.rule_id,
        "clause_number": rule.clause_number if rule else "N/A",
        "rule_content": rule.content if rule else "N/A",
        "review_type": rule.review_type if rule else None,
        "importance": rule.importance if rule else "中等",
        "result_code": result.result_code,
        "reasoning": result.reasoning,
        "evidence": result.evidence,
        "suggestion": result.suggestion,
        "created_at": result.created_at.isoformat()
    }


@app.put("/results/{result_id}")
def update_review_result(result_id: str, data: ResultUpdateRequest, session: Session = Depends(get_session)):
    """Update a review result item."""
    result = session.get(ReviewResultItem, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    # Validate result_code if provided
    if data.result_code:
        valid_codes = ["PASS", "REJECT", "MANUAL_CHECK"]
        if data.result_code not in valid_codes:
            raise HTTPException(status_code=400, detail=f"Invalid result_code. Must be one of: {valid_codes}")
        result.result_code = data.result_code

    if data.reasoning is not None:
        result.reasoning = data.reasoning
    if data.evidence is not None:
        result.evidence = data.evidence
    if data.suggestion is not None:
        result.suggestion = data.suggestion

    session.add(result)
    session.commit()
    session.refresh(result)

    rule = session.get(Rule, result.rule_id)
    return {
        "id": result.id,
        "task_id": result.task_id,
        "rule_id": result.rule_id,
        "clause_number": rule.clause_number if rule else "N/A",
        "rule_content": rule.content if rule else "N/A",
        "result_code": result.result_code,
        "reasoning": result.reasoning,
        "evidence": result.evidence,
        "suggestion": result.suggestion
    }


@app.delete("/results/{result_id}")
def delete_review_result(result_id: str, session: Session = Depends(get_session)):
    """Delete a single review result item."""
    result = session.get(ReviewResultItem, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    session.delete(result)
    session.commit()
    return {"message": "Result deleted successfully"}


# ============== Summary PDF Report Generation ==============

@app.get("/reviews/{task_id}/summary-pdf")
async def generate_summary_pdf(task_id: str, session: Session = Depends(get_session)):
    """Generate a summary PDF report for a review task (max 2 pages)."""
    from services import generate_summary_report_content

    task = session.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Task is not completed yet")

    # Get document and rule group info
    doc = session.get(Document, task.document_id)
    group = session.get(RuleGroup, task.rule_group_id)

    # Get all results with rule info
    results = session.exec(
        select(ReviewResultItem).where(ReviewResultItem.task_id == task_id)
    ).all()

    enriched_results = []
    for result in results:
        rule = session.get(Rule, result.rule_id)
        enriched_results.append({
            "clause_number": rule.clause_number if rule else "N/A",
            "rule_content": rule.content if rule else "N/A",
            "importance": rule.importance if rule else "中等",
            "result_code": result.result_code,
            "reasoning": result.reasoning,
            "evidence": result.evidence,
            "suggestion": result.suggestion
        })

    # Calculate stats
    stats = {"PASS": 0, "REJECT": 0, "MANUAL_CHECK": 0}
    for r in results:
        if r.result_code in stats:
            stats[r.result_code] += 1

    # Generate PDF using LLM for summary
    pdf_bytes = await generate_summary_report_content(
        document_name=doc.filename if doc else "Unknown",
        rule_group_name=group.name if group else "Unknown",
        total_rules=len(results),
        stats=stats,
        results=enriched_results
    )

    # Return as downloadable PDF
    safe_filename = f"review_summary_{task_id[:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"'
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

