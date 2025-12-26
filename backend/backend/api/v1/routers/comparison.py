from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException
from sqlmodel import Session
from backend.api.deps import get_session
from backend.models.comparison import ComparisonDocument, ComparisonResult
from backend.services.comparison_service import ComparisonService

router = APIRouter()

@router.get("/comparison-documents", response_model=List[ComparisonDocument])
def get_comparison_documents(session: Session = Depends(get_session)):
    """Get all comparison documents."""
    return ComparisonService.get_documents(session)

@router.get("/comparison-documents/{doc_id}", response_model=ComparisonDocument)
def get_comparison_document(doc_id: str, session: Session = Depends(get_session)):
    """Get a specific comparison document."""
    doc = ComparisonService.get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.post("/comparison-documents", response_model=ComparisonDocument)
async def upload_comparison_document(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session)
):
    """Upload a comparison document."""
    return await ComparisonService.upload_document(session, file, description, background_tasks)

@router.delete("/comparison-documents/{doc_id}")
async def delete_comparison_document(doc_id: str, session: Session = Depends(get_session)):
    """Delete a comparison document."""
    return await ComparisonService.delete_document(session, doc_id)
@router.get("/reviews/{task_id}/comparison-results", response_model=List[ComparisonResult])
def get_comparison_results(task_id: str, session: Session = Depends(get_session)):
    """Get comparison results for a review task."""
    return ComparisonService.get_results_by_task(session, task_id)
