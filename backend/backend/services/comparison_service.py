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
from backend.services.mineru_service import mineru_service
from backend.integrations.vector_store import ingest_chunks_to_chroma, delete_document_from_chroma, dynamic_chunk_text

async def process_comparison_document_background_from_file(doc_id: str, file_path: str, filename: str):
    """Background task to parse comparison document with MinerU and vectorize (reads from file)."""
    from sqlmodel import Session as SyncSession

    with SyncSession(engine) as session:
        doc = session.get(ComparisonDocument, doc_id)
        if not doc:
            print(f"Comparison Document {doc_id} not found for processing")
            return

        # Read file content from disk
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            doc.status = ComparisonDocumentStatus.FAILED.value
            doc.error_message = f"Failed to read file: {str(e)}"
            session.add(doc)
            session.commit()
            return

        try:
            # Update status to PARSING
            doc.status = ComparisonDocumentStatus.PARSING.value
            session.add(doc)
            session.commit()

            # Use MinerU to extract text
            print(f"Sending comparison document {filename} to MinerU for parsing...")
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
            markdown_filename = f"comp_{doc_id}.md"
            markdown_path = os.path.join(settings.UPLOADS_DIR, markdown_filename)
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            # Update document with markdown path and MinerU info
            doc.markdown_path = markdown_path
            doc.mineru_zip_url = result.get("zip_url")

            # Update description with basic info if empty
            if not doc.description:
                doc.description = f"Uploaded on {doc.upload_time.strftime('%Y-%m-%d %H:%M')}"

            session.add(doc)
            session.commit()

            print(f"Markdown saved to {markdown_path}, starting embedding...")

            # Update status to EMBEDDING
            doc.status = ComparisonDocumentStatus.EMBEDDING.value
            session.add(doc)
            session.commit()

            # Generate chunks from markdown
            chunks_data = dynamic_chunk_text(markdown_content)

            # Ingest to ChromaDB
            chunk_count = await ingest_chunks_to_chroma(doc_id, chunks_data, filename)

            # Update status to DONE
            doc.status = ComparisonDocumentStatus.DONE.value
            session.add(doc)
            session.commit()

            print(f"Successfully processed comparison document {filename} with {chunk_count} chunks")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error processing comparison document {filename}: {repr(e)}")
            doc.status = ComparisonDocumentStatus.FAILED.value
            doc.error_message = str(e)
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
        storage_filename = f"comp_{doc_id}{ext}"
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
        doc = ComparisonDocument(
            id=doc_id,
            filename=filename,
            storage_path=storage_path,
            description=description,
            status=ComparisonDocumentStatus.UPLOADING.value
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        # Start background processing with MinerU
        # Read file content in background to avoid blocking the response
        background_tasks.add_task(process_comparison_document_background_from_file, doc_id, storage_path, filename)

        return doc

    @staticmethod
    async def delete_document(session: Session, doc_id: str) -> dict:
        """Delete a comparison document, its markdown file, and its vectors."""
        doc = session.get(ComparisonDocument, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete from ChromaDB
        await delete_document_from_chroma(doc_id)

        # Delete original file from disk
        if doc.storage_path and os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
            except Exception as e:
                print(f"Warning: Could not delete file {doc.storage_path}: {e}")

        # Delete markdown file from disk
        if doc.markdown_path and os.path.exists(doc.markdown_path):
            try:
                os.remove(doc.markdown_path)
            except Exception as e:
                print(f"Warning: Could not delete markdown file {doc.markdown_path}: {e}")

        # Delete from database
        session.delete(doc)
        session.commit()

        return {"message": f"Comparison document '{doc.filename}' deleted successfully"}

    @staticmethod
    async def retry_document(session: Session, doc_id: str, background_tasks) -> ComparisonDocument:
        """Retry processing a failed comparison document."""
        doc = session.get(ComparisonDocument, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc.status != ComparisonDocumentStatus.FAILED.value:
            raise HTTPException(status_code=400, detail="Only failed documents can be retried")

        # Check if original file exists
        if not doc.storage_path or not os.path.exists(doc.storage_path):
            raise HTTPException(status_code=404, detail="Original file not found")

        # Reset status and error message
        doc.status = ComparisonDocumentStatus.UPLOADING.value
        doc.error_message = None
        session.add(doc)
        session.commit()
        session.refresh(doc)

        # Start background processing again (reads from file)
        background_tasks.add_task(process_comparison_document_background_from_file, doc_id, doc.storage_path, doc.filename)

        return doc
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
