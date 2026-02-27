from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session
from app.api.deps import get_session
from app.models.comparison import ComparisonDocument, ComparisonResult
from app.schemas.comparison import ComparisonResultRead
from app.services.comparison_service import ComparisonService
import os

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

@router.post("/comparison-documents/{doc_id}/retry", response_model=ComparisonDocument)
async def retry_comparison_document(
    doc_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session)
):
    """Retry processing a failed comparison document."""
    return await ComparisonService.retry_document(session, doc_id, background_tasks)

@router.get("/comparison-documents/{doc_id}/download-markdown")
async def download_comparison_markdown(doc_id: str, session: Session = Depends(get_session)):
    """Download the extracted markdown file for a comparison document."""
    doc = ComparisonService.get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.markdown_path or not os.path.exists(doc.markdown_path):
        raise HTTPException(status_code=404, detail="Markdown file not found")

    return FileResponse(
        path=doc.markdown_path,
        media_type="text/markdown",
        filename=f"{os.path.splitext(doc.filename)[0]}.md"
    )

@router.get("/comparison-documents/{doc_id}/download-original")
async def download_comparison_original(doc_id: str, session: Session = Depends(get_session)):
    """Download the original uploaded file for a comparison document."""
    doc = ComparisonService.get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.storage_path or not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="Original file not found")

    ext = os.path.splitext(doc.filename)[1].lower()
    media_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }
    media_type = media_types.get(ext, 'application/octet-stream')

    return FileResponse(
        path=doc.storage_path,
        media_type=media_type,
        filename=doc.filename
    )

@router.get("/reviews/{task_id}/comparison-results", response_model=List[ComparisonResultRead])
def get_comparison_results(task_id: str, session: Session = Depends(get_session)):
    """Get comparison results for a review task."""
    return ComparisonService.get_results_by_task(session, task_id)
