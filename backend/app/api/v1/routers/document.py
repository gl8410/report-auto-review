from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session
from app.api.deps import get_session, get_current_user
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.services.document_service import DocumentService
from app.models.user import Profile
import os

router = APIRouter()

@router.get("/documents", response_model=List[Document])
def get_documents(session: Session = Depends(get_session)):
    """Get all documents ordered by upload time (newest first)."""
    return DocumentService.get_documents(session)

@router.get("/documents/{doc_id}", response_model=Document)
def get_document(doc_id: str, session: Session = Depends(get_session)):
    """Get a specific document."""
    doc = DocumentService.get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/documents/{doc_id}/chunks", response_model=List[DocumentChunk])
def get_document_chunks(doc_id: str, session: Session = Depends(get_session)):
    """Get all chunks for a document."""
    return DocumentService.get_document_chunks(session, doc_id)

@router.post("/documents", response_model=Document)
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session),
    current_user: Profile = Depends(get_current_user)
):
    """Upload a document for review (supports .pdf, .docx, .doc)."""
    return await DocumentService.upload_document(session, file, background_tasks, owner_id=str(current_user.id))

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, session: Session = Depends(get_session)):
    """Delete a document and its vectors from ChromaDB."""
    return await DocumentService.delete_document(session, doc_id)

@router.post("/documents/{doc_id}/retry", response_model=Document)
async def retry_document(
    doc_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session)
):
    """Retry processing a failed document."""
    return await DocumentService.retry_document(session, doc_id, background_tasks)

@router.get("/documents/{doc_id}/download-markdown")
async def download_markdown(doc_id: str, session: Session = Depends(get_session)):
    """Download the extracted markdown file for a document."""
    doc = DocumentService.get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.markdown_path or not os.path.exists(doc.markdown_path):
        raise HTTPException(status_code=404, detail="Markdown file not found")

    # Return the markdown file
    return FileResponse(
        path=doc.markdown_path,
        media_type="text/markdown",
        filename=f"{os.path.splitext(doc.filename)[0]}.md"
    )

@router.get("/documents/{doc_id}/download-original")
async def download_original(doc_id: str, session: Session = Depends(get_session)):
    """Download the original uploaded file for a document."""
    doc = DocumentService.get_document(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.storage_path or not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="Original file not found")

    # Determine media type based on file extension
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