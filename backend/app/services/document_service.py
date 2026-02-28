import logging
import os
import uuid
import json
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from sqlmodel import Session, select
from app.core.config import settings
from app.core.db import engine
from app.models.document import Document, DocumentStatus
from app.models.chunk import DocumentChunk
from app.integrations.vector_store import ingest_chunks_to_chroma, delete_document_from_chroma, dynamic_chunk_text
from app.services.mineru_service import mineru_service

logger = logging.getLogger(__name__)


async def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """
    Extract text from a file using MinerU API.
    This is a helper function for temporary file uploads (analysis, rule imports, etc.)

    Args:
        file_content: The file content as bytes
        filename: The filename

    Returns:
        Extracted text content as markdown string

    Raises:
        HTTPException: If extraction fails
    """
    try:
        # Use MinerU to extract text
        files_data = [{
            "name": filename,
            "content": file_content,
            "data_id": str(uuid.uuid4())  # Temporary ID
        }]

        results = mineru_service.process_files(files_data)

        if not results or len(results) == 0:
            raise ValueError("No results returned from MinerU")

        result = results[0]

        if not result.get("success"):
            error_msg = result.get("error_message", "Unknown MinerU error")
            raise ValueError(f"MinerU parsing failed: {error_msg}")

        markdown_content = result.get("markdown_content", "")

        if not markdown_content:
            raise ValueError("No markdown content extracted from file")

        return markdown_content

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text from {filename}: {str(e)}"
        )

async def process_document_background_from_file(doc_id: str, file_path: str, filename: str):
    """Background task to parse document with MinerU and vectorize (reads from file)."""
    from sqlmodel import Session as SyncSession

    with SyncSession(engine) as session:
        doc = session.get(Document, doc_id)
        if not doc:
            logger.warning(f"Document {doc_id} not found for processing")
            return

        # Read file content from disk
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            doc.status = DocumentStatus.FAILED.value
            doc.error_message = f"Failed to read file: {str(e)}"
            session.add(doc)
            session.commit()
            return

        try:
            # Update status to PARSING
            doc.status = DocumentStatus.PARSING.value
            session.add(doc)
            session.commit()

            # Use MinerU to extract text
            files_data = [{
                "name": filename,
                "content": file_content,
                "data_id": doc_id
            }]

            results = mineru_service.process_files(files_data)

            if not results or len(results) == 0:
                raise ValueError("No results returned from MinerU")

            result = results[0]

            if not result.get("success"):
                error_msg = result.get("error_message", "Unknown MinerU error")
                raise ValueError(f"MinerU parsing failed: {error_msg}")

            markdown_content = result.get("markdown_content")
            if not markdown_content or len(markdown_content.strip()) < 10:
                raise ValueError("MinerU returned empty or invalid markdown content")

            # Save markdown file
            markdown_filename = f"{doc_id}.md"
            markdown_path = os.path.join(settings.UPLOADS_DIR, markdown_filename)
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            # Update document with markdown path and MinerU info
            doc.markdown_path = markdown_path
            doc.mineru_zip_url = result.get("zip_url")
            session.add(doc)
            session.commit()



            # Update status to EMBEDDING
            doc.status = DocumentStatus.EMBEDDING.value
            session.add(doc)
            session.commit()

            # Generate chunks from markdown
            chunks_data = dynamic_chunk_text(markdown_content)

            # Save chunks to SQL
            for chunk in chunks_data:
                db_chunk = DocumentChunk(
                    document_id=doc_id,
                    chunk_index=chunk["index"],
                    content=chunk["text"],
                    word_count=chunk["word_count"],
                    sentence_count=chunk["sentence_count"]
                )
                session.add(db_chunk)
            session.commit()

            # Ingest to ChromaDB
            chunk_count = await ingest_chunks_to_chroma(doc_id, chunks_data, filename)

            # Update status to DONE
            doc.status = DocumentStatus.DONE.value
            doc.meta_info = json.dumps({
                "text_length": len(markdown_content),
                "chunk_count": chunk_count,
                "filename": filename
            })
            session.add(doc)
            session.commit()
            
        except Exception as e:
            import traceback
            logger.error(f"Error processing document {filename}: {repr(e)}\n{traceback.format_exc()}")
            doc.status = DocumentStatus.FAILED.value
            doc.error_message = str(e)
            doc.meta_info = json.dumps({"error": str(e)})
            session.add(doc)
            session.commit()

class DocumentService:
    @staticmethod
    def get_documents(session: Session) -> List[Document]:
        """Get all documents ordered by upload time (newest first)."""
        return session.exec(select(Document).order_by(Document.upload_time.desc())).all()

    @staticmethod
    def get_document(session: Session, doc_id: str) -> Optional[Document]:
        """Get a specific document."""
        return session.get(Document, doc_id)

    @staticmethod
    def get_document_chunks(session: Session, doc_id: str) -> List[DocumentChunk]:
        """Get all chunks for a document."""
        return session.exec(select(DocumentChunk).where(DocumentChunk.document_id == doc_id).order_by(DocumentChunk.chunk_index)).all()

    @staticmethod
    async def upload_document(
        session: Session,
        file: UploadFile,
        background_tasks,
        owner_id: Optional[str] = None
    ) -> Document:
        """Upload a document for review (supports .pdf, .docx, .doc, .ppt, .pptx)."""
        filename = file.filename or "unknown"

        # Validate file type (MinerU supports more formats)
        valid_extensions = ['.pdf', '.docx', '.doc', '.ppt', '.pptx']
        ext = os.path.splitext(filename)[1].lower()
        if ext not in valid_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(valid_extensions)}"
            )

        # Ensure uploads directory exists
        os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

        # Generate unique filename for storage
        doc_id = str(uuid.uuid4())
        storage_filename = f"{doc_id}{ext}"
        storage_path = os.path.join(settings.UPLOADS_DIR, storage_filename)

        # Stream file to disk in chunks (optimized for large files)
        # This prevents loading the entire file into memory
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        try:
            with open(storage_path, 'wb') as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    file_size += len(chunk)

                    # Check file size limit during streaming (200MB for MinerU)
                    if file_size > 200 * 1024 * 1024:
                        # Clean up partial file
                        f.close()
                        if os.path.exists(storage_path):
                            os.remove(storage_path)
                        raise HTTPException(
                            status_code=400,
                            detail=f"File size exceeds 200MB limit. Current size: {file_size / 1024 / 1024:.2f}MB"
                        )
        except HTTPException:
            raise
        except Exception as e:
            # Clean up on error
            if os.path.exists(storage_path):
                os.remove(storage_path)
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

        # Validate final file size
        is_valid, error_msg = mineru_service.validate_file_size(file_size)
        if not is_valid:
            # Clean up file
            if os.path.exists(storage_path):
                os.remove(storage_path)
            raise HTTPException(status_code=400, detail=error_msg)

        # Create document record with UPLOADING status
        doc = Document(
            id=doc_id,
            filename=filename,
            storage_path=storage_path,
            status=DocumentStatus.UPLOADING.value,
            owner_id=str(owner_id) if owner_id else None
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        # Start background processing with MinerU
        # Read file content in background to avoid blocking the response
        background_tasks.add_task(process_document_background_from_file, doc_id, storage_path, filename)

        return doc

    @staticmethod
    async def delete_document(session: Session, doc_id: str) -> dict:
        """Delete a document, its markdown file, and its vectors from ChromaDB."""
        doc = session.get(Document, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete from ChromaDB
        await delete_document_from_chroma(doc_id)

        # Delete original file from disk
        if doc.storage_path and os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
            except Exception as e:
                logger.warning(f"Could not delete file {doc.storage_path}: {e}")

        # Delete markdown file from disk
        if doc.markdown_path and os.path.exists(doc.markdown_path):
            try:
                os.remove(doc.markdown_path)
            except Exception as e:
                logger.warning(f"Could not delete markdown file {doc.markdown_path}: {e}")

        # Delete from database
        session.delete(doc)
        session.commit()

        return {"message": f"Document '{doc.filename}' deleted successfully"}

    @staticmethod
    async def retry_document(session: Session, doc_id: str, background_tasks) -> Document:
        """Retry processing a failed document."""
        doc = session.get(Document, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc.status != DocumentStatus.FAILED.value:
            raise HTTPException(status_code=400, detail="Only failed documents can be retried")

        # Check if original file exists
        if not doc.storage_path or not os.path.exists(doc.storage_path):
            raise HTTPException(status_code=404, detail="Original file not found")

        # Reset status and error message
        doc.status = DocumentStatus.UPLOADING.value
        doc.error_message = None
        session.add(doc)
        session.commit()
        session.refresh(doc)

        # Start background processing again (reads from file)
        background_tasks.add_task(process_document_background_from_file, doc_id, doc.storage_path, doc.filename)

        return doc