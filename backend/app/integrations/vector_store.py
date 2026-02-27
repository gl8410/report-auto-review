import re
import httpx
import chromadb
from typing import List, Dict, Any, Optional
from app.core.config import settings

# ChromaDB client (singleton)
_chroma_client: Any = None

def get_chroma_client() -> Any:
    """Get ChromaDB client singleton"""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    return _chroma_client

# Document collection name
DOCUMENTS_COLLECTION = "documents"

async def get_embeddings(texts: List[str], batch_size: int = 2) -> List[List[float]]:
    """
    Get embeddings for a list of texts using SiliconFlow API.
    """
    if not settings.API_KEY:
        raise ValueError("API_KEY not found in environment variables")

    if not texts:
        return []

    headers = {
        "Authorization": f"Bearer {settings.API_KEY}",
        "Content-Type": "application/json"
    }

    timeout_config = httpx.Timeout(60.0, connect=10.0)
    all_embeddings: List[List[float]] = []

    async with httpx.AsyncClient(timeout=timeout_config) as client:
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            payload = {
                "model": settings.EMBEDDING_MODEL,
                "input": batch,
                "encoding_format": "float"
            }

            try:
                response = await client.post(settings.EMBEDDING_URL, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                # Extract embeddings from response
                batch_embeddings = [item["embedding"] for item in result["data"]]
                all_embeddings.extend(batch_embeddings)
            except httpx.HTTPStatusError as e:
                print(f"Embedding error for batch {i // batch_size + 1}: {e}")
                print(f"Response content: {e.response.text}")
                raise
            except Exception as e:
                print(f"Embedding error for batch {i // batch_size + 1}: {e}")
                import traceback
                traceback.print_exc()
                raise

    return all_embeddings

def dynamic_chunk_text(
    text: str,
    max_chunk_size: int = 2000,
    overlap_size: int = 200
) -> List[Dict[str, Any]]:
    """
    Enhanced Recursive Character Text Splitter.
    Prioritizes splitting by paragraphs, then sentences, then words.
    """
    separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
    
    def _split_text(text: str, separators: List[str]) -> List[str]:
        """Recursively split text using separators."""
        final_chunks = []
        separator = separators[-1]
        new_separators = []
        
        # Find the best separator to use
        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break
                
        # Split
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text) # Split by character if no separator found

        # Re-assemble chunks
        good_splits = []
        for s in splits:
            if s.strip():
                good_splits.append(s)
                
        current_chunk = []
        current_length = 0
        
        for split in good_splits:
            split_len = len(split)
            if separator:
                split_len += len(separator)
                
            if current_length + split_len > max_chunk_size:
                # If current chunk is not empty, save it
                if current_chunk:
                    text_chunk = separator.join(current_chunk)
                    if text_chunk.strip():
                        final_chunks.append(text_chunk)
                    current_chunk = []
                    current_length = 0
                
                # If the split itself is too big, recurse
                if split_len > max_chunk_size and new_separators:
                    sub_chunks = _split_text(split, new_separators)
                    final_chunks.extend(sub_chunks)
                else:
                    current_chunk.append(split)
                    current_length += split_len
            else:
                current_chunk.append(split)
                current_length += split_len
                
        if current_chunk:
            text_chunk = separator.join(current_chunk)
            if text_chunk.strip():
                final_chunks.append(text_chunk)
                
        return final_chunks

    # Initial split
    raw_chunks = _split_text(text, separators)
    
    processed_chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        if i > 0 and overlap_size > 0:
            prev_chunk = raw_chunks[i-1]
            overlap = prev_chunk[-overlap_size:]
            chunk_text = overlap + chunk_text
            
        processed_chunks.append({
            "text": chunk_text,
            "index": i,
            "word_count": len(chunk_text), # Approximation for Chinese
            "sentence_count": len(re.split(r'[。！？.!?]', chunk_text))
        })

    return processed_chunks

async def ingest_chunks_to_chroma(
    document_id: str,
    chunks: List[Dict[str, Any]],
    filename: str
) -> int:
    """
    Store pre-generated chunks in ChromaDB
    """
    if not chunks:
        return 0

    # Get embeddings for all chunks
    chunk_texts = [c["text"] for c in chunks]
    embeddings = await get_embeddings(chunk_texts)

    # Get or create collection
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=DOCUMENTS_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    # Prepare data for ChromaDB
    ids = [f"{document_id}_{c['index']}" for c in chunks]
    metadatas = [
        {
            "document_id": document_id,
            "filename": filename,
            "chunk_index": c["index"]
        }
        for c in chunks
    ]

    # Add to collection
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunk_texts,
        metadatas=metadatas
    )

    return len(chunks)

async def delete_document_from_chroma(document_id: str) -> bool:
    """
    Delete all chunks of a document from ChromaDB
    """
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(name=DOCUMENTS_COLLECTION)

        # Delete by document_id filter
        collection.delete(
            where={"document_id": document_id}
        )
        return True
    except Exception as e:
        print(f"Error deleting document from ChromaDB: {e}")
        return False

async def search_document_chunks(
    query: str,
    document_id: Optional[str] = None,
    n_results: int = 5
) -> List[Dict]:
    """
    Search for relevant document chunks
    """
    # Get query embedding
    query_embeddings = await get_embeddings([query])

    client = get_chroma_client()

    try:
        collection = client.get_collection(name=DOCUMENTS_COLLECTION)
    except Exception:
        return []

    # Build where filter
    where_filter = None
    if document_id:
        where_filter = {"document_id": document_id}

    # Search
    results = collection.query(
        query_embeddings=query_embeddings,
        n_results=n_results,
        where=where_filter
    )

    # Format results
    formatted_results = []
    if results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            formatted_results.append({
                "text": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None
            })

    return formatted_results