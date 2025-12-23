from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlmodel import Session
from backend.api.deps import get_session
from backend.models.document import Document
from backend.models.chunk import DocumentChunk
from backend.services.document_service import DocumentService

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
    session: Session = Depends(get_session)
):
    """Upload a document for review (supports .pdf, .docx, .doc)."""
    return await DocumentService.upload_document(session, file, background_tasks)

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, session: Session = Depends(get_session)):
    """Delete a document and its vectors from ChromaDB."""
    return await DocumentService.delete_document(session, doc_id)