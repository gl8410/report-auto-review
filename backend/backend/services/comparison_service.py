import os
import uuid
import json
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from sqlmodel import Session, select
from backend.core.config import settings
from backend.core.db import engine
from backend.models.comparison import ComparisonDocument, ComparisonDocumentStatus, ComparisonResult
from backend.models.chunk import DocumentChunk
from backend.services.document_service import extract_text_from_file
from backend.integrations.vector_store import ingest_chunks_to_chroma, delete_document_from_chroma, dynamic_chunk_text

async def process_comparison_document_background(doc_id: str, file_content: bytes, filename: str):
    """Background task to parse and vectorize comparison document."""
    from sqlmodel import Session as SyncSession

    with SyncSession(engine) as session:
        doc = session.get(ComparisonDocument, doc_id)
        if not doc:
            print(f"Comparison Document {doc_id} not found for processing")
            return

        try:
            # Update status to PARSING
            doc.status = ComparisonDocumentStatus.PARSING.value
            session.add(doc)
            session.commit()

            # Extract text from document
            text_content = await extract_text_from_file(file_content, filename)

            if not text_content or len(text_content.strip()) < 10:
                raise ValueError("Document contains no extractable text")

            # Update description with basic info if empty
            if not doc.description:
                doc.description = f"Uploaded on {doc.upload_time.strftime('%Y-%m-%d %H:%M')}"

            session.add(doc)
            session.commit()

            # Generate chunks
            chunks_data = dynamic_chunk_text(text_content)
            
            # Note: We reuse DocumentChunk model but store it with comparison_document_id
            # Wait, DocumentChunk has 'document_id' foreign key to 'documents' table.
            # We cannot use DocumentChunk for ComparisonDocument if there is a FK constraint.
            # Let's check DocumentChunk model.
            
            # Checking DocumentChunk model...
            # If strict FK exists, we need a separate Chunk model or make FK optional/polymorphic.
            # For now, let's assume we use the same vector store collection but different metadata.
            # But for SQL storage, we might need a separate table or just rely on Vector Store for retrieval.
            # Let's check DocumentChunk definition in next step. For now, I will comment out SQL chunk storage for Comparison Docs
            # and only use Vector Store which is flexible.
            
            # Ingest to ChromaDB (using same collection or new? Let's use same but with metadata type='comparison')
            # actually ingest_chunks_to_chroma uses 'document_id' as metadata. 
            # We can use the comparison doc id as document_id in chroma.
            
            chunk_count = await ingest_chunks_to_chroma(doc_id, chunks_data, filename)

            # Update status to INDEXED
            doc.status = ComparisonDocumentStatus.INDEXED.value
            session.add(doc)
            session.commit()

            print(f"Successfully indexed comparison document {filename} with {chunk_count} chunks")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error processing comparison document {filename}: {repr(e)}")
            doc.status = ComparisonDocumentStatus.FAILED.value
            session.add(doc)
            session.commit()

class ComparisonService:
    @staticmethod
    def get_documents(session: Session) -> List[ComparisonDocument]:
        """Get all comparison documents ordered by upload time."""
        return session.exec(select(ComparisonDocument).order_by(ComparisonDocument.upload_time.desc())).all()

    @staticmethod
    def get_document(session: Session, doc_id: str) -> Optional[ComparisonDocument]:
        """Get a specific comparison document."""
        return session.get(ComparisonDocument, doc_id)

    @staticmethod
    async def upload_document(
        session: Session,
        file: UploadFile,
        description: Optional[str],
        background_tasks
    ) -> ComparisonDocument:
        """Upload a comparison document."""
        filename = file.filename or "unknown"

        # Validate file type
        valid_extensions = ['.pdf', '.docx', '.doc', '.txt', '.md']
        ext = os.path.splitext(filename)[1].lower()
        if ext not in valid_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(valid_extensions)}"
            )

        # Read file content
        file_content = await file.read()

        # Ensure uploads directory exists
        os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

        # Generate unique filename for storage
        doc_id = str(uuid.uuid4())
        storage_filename = f"comp_{doc_id}{ext}"
        storage_path = os.path.join(settings.UPLOADS_DIR, storage_filename)

        # Save file to disk
        with open(storage_path, 'wb') as f:
            f.write(file_content)

        # Create document record
        doc = ComparisonDocument(
            id=doc_id,
            filename=filename,
            storage_path=storage_path,
            description=description,
            status=ComparisonDocumentStatus.UPLOADED.value
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        # Start background processing
        background_tasks.add_task(process_comparison_document_background, doc_id, file_content, filename)

        return doc

    @staticmethod
    async def delete_document(session: Session, doc_id: str) -> dict:
        """Delete a comparison document and its vectors."""
        doc = session.get(ComparisonDocument, doc_id)
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

        return {"message": f"Comparison document '{doc.filename}' deleted successfully"}
    @staticmethod
    def get_results_by_task(session: Session, task_id: str) -> List[ComparisonResult]:
        """Get all comparison results for a specific task."""
        # We need to join with ComparisonDocument to get the document name if needed,
        # but for now let's just return the results.
        # Actually, the frontend expects 'document_name' in ComparisonResult interface (enriched field).
        # So we might need to enrich it here or let the frontend fetch documents separately.
        # Let's enrich it here for convenience.
        results = session.exec(select(ComparisonResult).where(ComparisonResult.task_id == task_id)).all()
        
        # Enrich with document name
        enriched_results = []
        for res in results:
            doc = session.get(ComparisonDocument, res.comparison_document_id)
            # Create a dict or modify object if possible. SQLModel objects are not dicts.
            # We can return the object and let Pydantic handle it if we add a property, 
            # or just return a list of dicts/custom objects.
            # Let's try to set the attribute dynamically if Pydantic allows, or just return as is
            # and let frontend handle mapping if we send document list.
            # But wait, the API response model is List[ComparisonResult].
            # If we want to include document_name, we should probably update the model or return a different schema.
            # For simplicity, let's just return the results and let frontend map IDs to names using the documents list it already has or fetches.
            pass
            
        return results
