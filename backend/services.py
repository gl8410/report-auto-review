"""
LLM Service for rule parsing using DeepSeek V3.1 via SiliconFlow API.
Also includes document text extraction, chunking, and ChromaDB vectorization.
"""
import os
import io
import json
import re
import uuid
import httpx
import chromadb
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

API_KEY = os.getenv("API_KEY")
LLM_URL = os.getenv("LLM_URL", "https://api.siliconflow.cn/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "Pro/deepseek-ai/DeepSeek-V3.1-Terminus")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "https://api.siliconflow.cn/v1/embeddings")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))

# ChromaDB client (singleton)
_chroma_client: Optional[chromadb.HttpClient] = None

def get_chroma_client() -> chromadb.HttpClient:
    """Get ChromaDB client singleton"""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return _chroma_client

# Document collection name
DOCUMENTS_COLLECTION = "documents"

# Valid values for rule fields
VALID_REVIEW_TYPES = ["内容完整性", "计算结果准确性", "禁止条款", "前后逻辑一致性", "措施遵从性", "计算正确性"]
# Valid risk levels
VALID_RISK_LEVELS = ["低风险", "中风险", "高风险"]


# ============== Pydantic Schemas for LLM Output ==============

class ParsedRule(BaseModel):
    """LLM解析出的单条规则"""
    clause_number: str = Field(..., description="条文号，如 3.1.2")
    content: str = Field(..., description="规则具体内容")
    review_type: str = Field(
        default="内容完整性",
        description="审查类型：内容完整性/计算结果准确性/禁止条款/前后逻辑一致性/措施遵从性/计算正确性"
    )
    risk_level: str = Field(
        default="中风险",
        description="风险等级：低风险/中风险/高风险"
    )


class ParsedRulesResponse(BaseModel):
    """LLM解析规则的响应"""
    standard_name: str = Field(..., description="标准/导则名称")
    rules: List[ParsedRule] = Field(default_factory=list, description="解析出的规则列表")


# ============== LLM Service ==============

async def call_llm(
    messages: List[Dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 4096
) -> Optional[str]:
    """
    调用DeepSeek V3.1 LLM API
    
    Args:
        messages: 对话消息列表
        temperature: 采样温度
        max_tokens: 最大生成tokens
        
    Returns:
        LLM生成的文本响应
    """
    if not API_KEY:
        raise ValueError("API_KEY not found in environment variables")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    # Use longer timeout for LLM calls - large documents may take time
    timeout_config = httpx.Timeout(300.0, connect=30.0)  # 5 minutes total, 30s connect

    async with httpx.AsyncClient(timeout=timeout_config) as client:
        try:
            response = await client.post(LLM_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except httpx.ReadTimeout:
            raise Exception("LLM服务响应超时，请稍后重试或尝试上传较小的文件")
        except httpx.ConnectTimeout:
            raise Exception("无法连接到LLM服务，请检查网络连接")
        except httpx.HTTPStatusError as e:
            raise Exception(f"LLM服务返回错误: {e.response.status_code}")


async def extract_text_from_file(content: bytes, filename: str) -> str:
    """
    从不同格式的文件中提取文本内容

    Args:
        content: 文件二进制内容
        filename: 文件名（用于判断文件类型）

    Returns:
        提取的文本内容
    """
    filename_lower = filename.lower()

    if filename_lower.endswith('.pdf'):
        # Extract text from PDF
        try:
            from pypdf import PdfReader
            pdf_reader = PdfReader(io.BytesIO(content))
            text_parts = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n".join(text_parts)
        except Exception as e:
            print(f"PDF extraction error: {e}")
            raise ValueError(f"Failed to extract text from PDF: {e}")

    elif filename_lower.endswith('.docx'):
        # Extract text from DOCX
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)
            return "\n".join(text_parts)
        except Exception as e:
            print(f"DOCX extraction error: {e}")
            raise ValueError(f"Failed to extract text from DOCX: {e}")

    else:
        # Plain text files (.txt, .md)
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            return content.decode('gbk', errors='ignore')


async def parse_rules_from_text(text: str, filename: str = "") -> ParsedRulesResponse:
    """
    使用LLM从文本中解析规则

    Args:
        text: 原始法规/标准文本
        filename: 文件名（用于提取标准名称）

    Returns:
        ParsedRulesResponse 包含解析出的规则列表
    """
    system_prompt = """你是一个专业的法规条文解析助手。你的任务是将上传的法规/标准文本拆解为原子化的审查规则。

请严格按照以下JSON格式输出：
{
    "standard_name": "标准/导则的完整名称",
    "rules": [
        {
            "clause_number": "条文号，如 3.1.2 或 第三条",
            "content": "该条规则的具体内容，保持原文",
            "review_type": "审查类型，必须从以下六种中选择一种：内容完整性/计算结果准确性/禁止条款/前后逻辑一致性/措施遵从性/计算正确性",
            "risk_level": "风险等级，必须从以下三种中选择一种：低风险/中风险/高风险"
        }
    ]
}

【审查类型判断标准】
- 内容完整性：要求报告必须包含某些章节、内容或信息
- 计算结果准确性：涉及数值计算结果的校核
- 禁止条款：明确禁止某些做法的强制性条款（如"不得"、"严禁"等）
- 前后逻辑一致性：要求文档内部数据、结论等前后一致
- 措施遵从性：要求采取特定的工程措施或方法
- 计算正确性：涉及计算方法、公式的正确使用

【风险等级判断标准】
- 高风险：强制性条款、涉及安全的条款、使用"必须"、"严禁"、"不得"等词
- 中风险：一般性要求、使用"应"、"应当"等词
- 低风险：建议性条款、使用"宜"、"可"等词

【重要提醒】
1. review_type 必须是上述6种之一，不能自创
2. risk_level 必须是：低风险、中风险、高风险 之一
3. clause_number 保持原文格式
4. 只输出JSON，不要其他解释文字"""

    user_prompt = f"""请解析以下法规/标准文本，将其拆解为原子化规则：

文件名：{filename}

文本内容：
{text[:15000]}"""  # Limit text length to avoid token limits

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = await call_llm(messages, temperature=0.2, max_tokens=8000)

        if not response:
            raise ValueError("LLM returned empty response")

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        # Parse JSON
        data = json.loads(json_str)

        # Validate and normalize the parsed data
        parsed_response = ParsedRulesResponse(**data)

        # Validate each rule's review_type and importance
        validated_rules = []
        for rule in parsed_response.rules:
            # Normalize review_type
            if rule.review_type not in VALID_REVIEW_TYPES:
                rule.review_type = "内容完整性"  # Default fallback
            # Normalize risk_level
            if rule.risk_level not in VALID_RISK_LEVELS:
                # Try to map old values or English values
                risk_map = {
                    "High": "高风险", "Medium": "中风险", "Low": "低风险",
                    "重要": "高风险", "中等": "中风险", "一般": "低风险"
                }
                rule.risk_level = risk_map.get(rule.risk_level, "中风险")
            validated_rules.append(rule)

        parsed_response.rules = validated_rules
        return parsed_response

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Response was: {response[:500] if response else 'None'}")
        # Try to repair truncated JSON
        try:
            # Sometimes LLM output is truncated, try to extract what we can
            # Find all complete rule objects
            rule_pattern = r'\{\s*"clause_number"\s*:\s*"([^"]+)"\s*,\s*"content"\s*:\s*"([^"]+)"\s*,\s*"review_type"\s*:\s*"([^"]+)"\s*,\s*"risk_level"\s*:\s*"([^"]+)"\s*\}'
            matches = re.findall(rule_pattern, response or "")
            if matches:
                print(f"Recovered {len(matches)} rules from malformed JSON")
                rules = []
                for match in matches:
                    rule = ParsedRule(
                        clause_number=match[0],
                        content=match[1],
                        review_type=match[2] if match[2] in VALID_REVIEW_TYPES else "内容完整性",
                        risk_level=match[3] if match[3] in VALID_RISK_LEVELS else "中风险"
                    )
                    rules.append(rule)
                # Extract standard_name if possible
                standard_match = re.search(r'"standard_name"\s*:\s*"([^"]+)"', response or "")
                standard_name = standard_match.group(1) if standard_match else filename
                return ParsedRulesResponse(standard_name=standard_name, rules=rules)
        except Exception as recovery_error:
            print(f"Recovery failed: {recovery_error}")

        # If recovery fails, raise exception instead of silent failure
        raise ValueError(f"无法解析LLM返回的规则数据: {e}")
    except Exception as e:
        print(f"LLM call error: {e}")
        raise


async def health_check_llm() -> bool:
    """检查LLM服务是否可用"""
    try:
        response = await call_llm(
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        return response is not None
    except Exception:
        return False


# ============== Embedding Service ==============

async def get_embeddings(texts: List[str], batch_size: int = 2) -> List[List[float]]:
    """
    Get embeddings for a list of texts using SiliconFlow API.
    Batches requests to avoid 413 Request Entity Too Large errors.

    Args:
        texts: List of text strings to embed
        batch_size: Number of texts to process in each API call (default: 10)

    Returns:
        List of embedding vectors
    """
    if not API_KEY:
        raise ValueError("API_KEY not found in environment variables")

    if not texts:
        return []

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    timeout_config = httpx.Timeout(60.0, connect=10.0)
    all_embeddings: List[List[float]] = []

    async with httpx.AsyncClient(timeout=timeout_config) as client:
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            payload = {
                "model": EMBEDDING_MODEL,
                "input": batch,
                "encoding_format": "float"
            }

            try:
                response = await client.post(EMBEDDING_URL, json=payload, headers=headers)
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


# ============== Document Chunking ==============

def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences using common Chinese and English delimiters.
    """
    # Chinese and English sentence delimiters
    delimiters = r'[。！？!?；;]'

    # Split but keep delimiters
    parts = re.split(f'({delimiters})', text)

    sentences = []
    current = ""
    for i, part in enumerate(parts):
        current += part
        # If this is a delimiter, complete the sentence
        if re.match(delimiters, part):
            if current.strip():
                sentences.append(current.strip())
            current = ""

    # Add remaining text if any
    if current.strip():
        sentences.append(current.strip())

    return sentences


def dynamic_chunk_text(
    text: str,
    max_chunk_size: int = 2000,
    min_chunk_size: int = 200,
    overlap_sentences: int = 2
) -> List[Dict[str, Any]]:
    """
    Dynamic chunking strategy that respects semantic boundaries.

    Uses Qwen3-Embedding-8B's larger context window (8K tokens) with
    chunks of ~2000 chars (~600-800 tokens for Chinese text).

    Strategy:
    1. First split by double newlines (paragraphs)
    2. If paragraph too large, split by sentences
    3. Merge small chunks to reach min_chunk_size
    4. Add sentence-level overlap for context continuity

    Args:
        text: The full document text
        max_chunk_size: Maximum chunk size in characters (default: 2000)
        min_chunk_size: Minimum chunk size in characters (default: 200)
        overlap_sentences: Number of sentences to overlap between chunks

    Returns:
        List of chunk dictionaries with 'text' and 'index'
    """
    chunks = []
    chunk_index = 0

    # Step 1: Split by paragraphs (double newlines or single newlines)
    paragraphs = re.split(r'\n\s*\n|\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    current_chunk_parts = []
    current_size = 0
    overlap_buffer = []  # Stores last few sentences for overlap

    for para in paragraphs:
        para_size = len(para)

        # If single paragraph exceeds max, split by sentences
        if para_size > max_chunk_size:
            # First, save current chunk if exists
            if current_chunk_parts:
                chunk_text = '\n'.join(current_chunk_parts)
                if chunk_text.strip():
                    chunks.append({
                        "text": chunk_text.strip(),
                        "index": chunk_index
                    })
                    chunk_index += 1
                    # Update overlap buffer
                    overlap_buffer = split_into_sentences(chunk_text)[-overlap_sentences:]
                current_chunk_parts = []
                current_size = 0

            # Split large paragraph into sentences
            sentences = split_into_sentences(para)
            sent_chunk = list(overlap_buffer)  # Start with overlap
            sent_size = sum(len(s) for s in sent_chunk)

            for sent in sentences:
                if sent_size + len(sent) > max_chunk_size and sent_chunk:
                    # Save current sentence chunk
                    chunk_text = ' '.join(sent_chunk)
                    if chunk_text.strip():
                        chunks.append({
                            "text": chunk_text.strip(),
                            "index": chunk_index
                        })
                        chunk_index += 1
                    # Keep overlap
                    overlap_buffer = sent_chunk[-overlap_sentences:] if len(sent_chunk) > overlap_sentences else sent_chunk
                    sent_chunk = list(overlap_buffer) + [sent]
                    sent_size = sum(len(s) for s in sent_chunk)
                else:
                    sent_chunk.append(sent)
                    sent_size += len(sent)

            # Add remaining sentences to current_chunk_parts
            if sent_chunk:
                current_chunk_parts = [' '.join(sent_chunk)]
                current_size = sum(len(s) for s in sent_chunk)
                overlap_buffer = sent_chunk[-overlap_sentences:] if len(sent_chunk) > overlap_sentences else sent_chunk

        # If adding paragraph exceeds max, save current and start new
        elif current_size + para_size + 1 > max_chunk_size and current_chunk_parts:
            chunk_text = '\n'.join(current_chunk_parts)
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text.strip(),
                    "index": chunk_index
                })
                chunk_index += 1
                # Update overlap buffer
                overlap_buffer = split_into_sentences(chunk_text)[-overlap_sentences:]

            # Start new chunk with overlap
            if overlap_buffer:
                overlap_text = ' '.join(overlap_buffer)
                current_chunk_parts = [overlap_text, para]
                current_size = len(overlap_text) + para_size + 1
            else:
                current_chunk_parts = [para]
                current_size = para_size
        else:
            # Add to current chunk
            current_chunk_parts.append(para)
            current_size += para_size + 1

    # Add final chunk
    if current_chunk_parts:
        chunk_text = '\n'.join(current_chunk_parts)
        if chunk_text.strip():
            chunks.append({
                "text": chunk_text.strip(),
                "index": chunk_index
            })

    # Merge very small chunks
    merged_chunks = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        # If current chunk is too small and not the last one, try to merge
        while len(current["text"]) < min_chunk_size and i + 1 < len(chunks):
            i += 1
            current = {
                "text": current["text"] + "\n" + chunks[i]["text"],
                "index": current["index"]
            }
        merged_chunks.append(current)
        i += 1

    # Re-index merged chunks
    for idx, chunk in enumerate(merged_chunks):
        chunk["index"] = idx

    return merged_chunks


# Alias for backward compatibility
def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 100) -> List[Dict[str, Any]]:
    """Backward compatible wrapper for dynamic_chunk_text"""
    return dynamic_chunk_text(text, max_chunk_size=chunk_size, min_chunk_size=200, overlap_sentences=2)


# ============== ChromaDB Document Ingestion ==============

async def ingest_document_to_chroma(
    document_id: str,
    text: str,
    filename: str
) -> int:
    """
    Process document text and store chunks in ChromaDB

    Args:
        document_id: UUID of the document
        text: Full document text
        filename: Original filename

    Returns:
        Number of chunks stored
    """
    # Chunk the text using dynamic chunking (2000 chars max for Qwen3-Embedding-8B)
    chunks = dynamic_chunk_text(text, max_chunk_size=2000, min_chunk_size=200, overlap_sentences=2)

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

    Args:
        document_id: UUID of the document to delete

    Returns:
        True if successful
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

    Args:
        query: Search query text
        document_id: Optional filter by specific document
        n_results: Number of results to return

    Returns:
        List of matching chunks with metadata
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


# ============== Review Execution Service ==============

async def generate_review_queries(rule_content: str, review_type: str = "") -> List[str]:
    """
    Generate multiple optimized search queries from rule content for vector retrieval.
    Uses LLM to extract key concepts that should appear in actual document content (not just titles).

    Returns:
        List of search queries to use for retrieval
    """
    # Use LLM to generate targeted search queries
    prompt = f"""你是一个文档检索专家。给定以下审查规则，请生成2-3个搜索查询词，用于在工程报告中检索相关的实际内容（不是目录标题）。

规则内容：{rule_content[:800]}
审查类型：{review_type}

要求：
1. 提取规则中的关键技术概念和数据类型
2. 生成的查询应该能匹配到文档中的具体分析内容、计算过程、数据表格
3. 避免只匹配到目录或章节标题
4. 每个查询词控制在50字以内

请直接返回JSON数组格式，例如：
["水文分析计算结果 洪峰流量", "壅水高度计算 水位变化", "冲刷深度分析数据"]"""

    try:
        messages = [
            {"role": "system", "content": "你是一个专业的文档检索助手，帮助生成精确的搜索查询。"},
            {"role": "user", "content": prompt}
        ]

        response = await call_llm(messages, temperature=0.3, max_tokens=500)

        if response:
            # Extract JSON array from response
            json_match = re.search(r'\[[\s\S]*?\]', response)
            if json_match:
                queries = json.loads(json_match.group())
                if isinstance(queries, list) and len(queries) > 0:
                    # Add the original rule content as a fallback query
                    queries.append(rule_content[:300])
                    return queries[:4]  # Limit to 4 queries
    except Exception as e:
        print(f"Error generating search queries: {e}")

    # Fallback: return original rule content split into key phrases
    return [rule_content[:300]]


async def generate_review_query(rule_content: str) -> str:
    """
    Generate an optimized search query from rule content for vector retrieval.
    (Legacy function for backward compatibility)
    """
    return rule_content[:500]


async def compare_rule_with_context(
    rule: Dict[str, Any],
    context_chunks: List[Dict],
    document_filename: str
) -> Dict[str, Any]:
    """
    Use LLM to compare a rule against retrieved document context.

    Args:
        rule: The rule to check (dict with content, clause_number, etc.)
        context_chunks: Retrieved document chunks
        document_filename: Name of the document being reviewed

    Returns:
        Dict with result_code, reasoning, evidence, suggestion
    """
    if not API_KEY:
        raise ValueError("API_KEY not found")

    # Combine context chunks
    context_text = "\n\n---\n\n".join([
        f"[片段 {i+1}]\n{chunk['text']}"
        for i, chunk in enumerate(context_chunks)
    ])

    if not context_text.strip():
        context_text = "（未找到相关内容）"

    prompt = f"""你是一名专业的工程报告审查专家。请根据以下规则条款，审查文档中的相关内容是否符合要求。

## 规则信息
- 条文号: {rule.get('clause_number', 'N/A')}
- 规则内容: {rule.get('content', '')}
- 审查类型: {rule.get('review_type', '未指定')}
- 风险等级: {rule.get('risk_level', '中风险')}

## 文档名称
{document_filename}

## 文档相关内容
{context_text}

## 审查要求
请仔细分析文档内容是否符合上述规则要求，并给出审查结论。

请严格按照以下JSON格式输出（不要添加任何其他内容）：
{{
    "result_code": "PASS/REJECT/MANUAL_CHECK",
    "reasoning": "详细的判断理由，说明为什么得出该结论",
    "evidence": "引用文档中的相关原文作为证据（如有）",
    "suggestion": "如果不符合要求，给出具体的修改建议；如符合则填写'无'"
}}

注意：
- PASS: 文档内容完全符合规则要求
- REJECT: 文档内容明确不符合规则要求
- MANUAL_CHECK: 无法确定是否符合，需要人工复核（如找不到相关内容、信息不足等）
"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,  # Low temperature for consistent results
        "max_tokens": 1000
    }

    timeout_config = httpx.Timeout(120.0, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout_config) as client:
        try:
            response = await client.post(LLM_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

            content = result["choices"][0]["message"]["content"]

            # Parse JSON response
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())

                # Validate result_code
                valid_codes = ["PASS", "REJECT", "MANUAL_CHECK"]
                if parsed.get("result_code") not in valid_codes:
                    parsed["result_code"] = "MANUAL_CHECK"

                return {
                    "result_code": parsed.get("result_code", "MANUAL_CHECK"),
                    "reasoning": parsed.get("reasoning", "无法解析审查结果"),
                    "evidence": parsed.get("evidence", ""),
                    "suggestion": parsed.get("suggestion", "")
                }
            else:
                return {
                    "result_code": "MANUAL_CHECK",
                    "reasoning": f"LLM响应格式异常: {content[:200]}",
                    "evidence": "",
                    "suggestion": "请人工审查"
                }

        except Exception as e:
            print(f"Review comparison error: {e}")
            return {
                "result_code": "MANUAL_CHECK",
                "reasoning": f"审查过程出错: {str(e)}",
                "evidence": "",
                "suggestion": "请人工审查"
            }


async def execute_review_for_rule(
    rule: Dict[str, Any],
    document_id: str,
    document_filename: str
) -> Dict[str, Any]:
    """
    Execute review for a single rule against a document.
    Uses multi-query retrieval strategy to find actual content (not just TOC).

    Args:
        rule: Rule dict with id, content, clause_number, etc.
        document_id: UUID of the document
        document_filename: Name of the document

    Returns:
        Review result dict
    """
    # Step 1: Generate multiple search queries from rule (LLM-enhanced)
    search_queries = await generate_review_queries(
        rule.get("content", ""),
        rule.get("review_type", "")
    )

    print(f"  Generated {len(search_queries)} search queries for rule {rule.get('clause_number', 'N/A')}")

    # Step 2: Retrieve relevant document chunks using all queries
    all_chunks = []
    seen_texts = set()  # Deduplicate chunks

    for query in search_queries:
        chunks = await search_document_chunks(
            query=query,
            document_id=document_id,
            n_results=5  # 5 per query, up to 20 total before dedup
        )
        for chunk in chunks:
            # Deduplicate based on text content
            chunk_text = chunk.get("text", "")[:200]  # Use first 200 chars as key
            if chunk_text not in seen_texts:
                seen_texts.add(chunk_text)
                all_chunks.append(chunk)

    # Sort by relevance (distance) and take top 10
    all_chunks.sort(key=lambda x: x.get("distance", 1.0))
    context_chunks = all_chunks[:10]

    print(f"  Retrieved {len(context_chunks)} unique chunks (from {len(all_chunks)} total)")

    # Step 3: Compare rule with context using LLM
    result = await compare_rule_with_context(
        rule=rule,
        context_chunks=context_chunks,
        document_filename=document_filename
    )

    return result


# ============== PDF Summary Report Generation ==============

async def generate_summary_report_content(
    document_name: str,
    rule_group_name: str,
    total_rules: int,
    stats: Dict[str, int],
    results: List[Dict[str, Any]]
) -> bytes:
    """
    Generate a 2-page PDF summary report for review results.
    Uses LLM to generate the summary text, then creates PDF.

    Args:
        document_name: Name of the reviewed document
        rule_group_name: Name of the rule group used
        total_rules: Total number of rules reviewed
        stats: Dict with PASS, REJECT, MANUAL_CHECK counts
        results: List of review result dicts

    Returns:
        PDF file as bytes
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from datetime import datetime

    # Register Chinese font
    font_registered = False
    try:
        # Try to use system Chinese font
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # Windows Microsoft YaHei
            "C:/Windows/Fonts/simsun.ttc",  # Windows SimSun
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Linux
            "/System/Library/Fonts/PingFang.ttc",  # macOS
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                font_registered = True
                break
    except Exception as e:
        print(f"Font registration error: {e}")

    # Separate results by risk_level and result_code
    serious_problems = [r for r in results if r["result_code"] == "REJECT" and r.get("risk_level") == "高风险"]
    medium_problems = [r for r in results if r["result_code"] == "REJECT" and r.get("risk_level") != "高风险"]
    manual_checks = [r for r in results if r["result_code"] == "MANUAL_CHECK"]

    # Generate LLM summary
    summary_prompt = f"""你是一个工程报告审查专家。请根据以下审查结果生成一份简洁的审查摘要（200字以内）：

**审查文档**: {document_name}
**规则组**: {rule_group_name}
**总规则数**: {total_rules}
**通过**: {stats['PASS']}条
**不通过**: {stats['REJECT']}条
**待人工复核**: {stats['MANUAL_CHECK']}条

**主要问题**:
{chr(10).join([f"- 条款{r['clause_number']}: {r['reasoning'][:100]}..." for r in serious_problems[:5]]) if serious_problems else "无严重问题"}

请生成一段专业的审查总结，包括：总体评价、主要发现、建议。直接输出摘要文字，不要有任何前缀。"""

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                LLM_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": summary_prompt}],
                    "temperature": 0.3,
                    "max_tokens": 500
                }
            )
            response.raise_for_status()
            llm_summary = response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"LLM summary generation error: {e}")
        llm_summary = f"审查完成。共审查{total_rules}条规则，通过{stats['PASS']}条，不通过{stats['REJECT']}条，待人工复核{stats['MANUAL_CHECK']}条。"

    # Create PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    # Styles
    styles = getSampleStyleSheet()
    try:
        title_style = ParagraphStyle(
            'ChineseTitle',
            parent=styles['Heading1'],
            fontName='ChineseFont',
            fontSize=18,
            spaceAfter=12,
            alignment=1  # Center
        )
        heading_style = ParagraphStyle(
            'ChineseHeading',
            parent=styles['Heading2'],
            fontName='ChineseFont',
            fontSize=14,
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'ChineseBody',
            parent=styles['Normal'],
            fontName='ChineseFont',
            fontSize=10,
            leading=14,
            spaceAfter=6
        )
        small_style = ParagraphStyle(
            'ChineseSmall',
            parent=styles['Normal'],
            fontName='ChineseFont',
            fontSize=9,
            leading=12
        )
    except:
        # Fallback to default styles
        title_style = styles['Heading1']
        heading_style = styles['Heading2']
        body_style = styles['Normal']
        small_style = styles['Normal']

    story = []

    # Title
    story.append(Paragraph("文档审查报告摘要", title_style))
    story.append(Spacer(1, 10*mm))

    # Document info
    story.append(Paragraph(f"<b>审查文档：</b>{document_name}", body_style))
    story.append(Paragraph(f"<b>规则组：</b>{rule_group_name}", body_style))
    story.append(Paragraph(f"<b>生成时间：</b>{datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
    story.append(Spacer(1, 5*mm))

    # Stats table - use Paragraph for Chinese text in cells
    font_name = 'ChineseFont' if font_registered else 'Helvetica'
    stats_data = [
        [Paragraph("总规则数", ParagraphStyle('TableHeader', fontName=font_name, fontSize=10, textColor=colors.white, alignment=1)),
         Paragraph("通过", ParagraphStyle('TableHeader', fontName=font_name, fontSize=10, textColor=colors.white, alignment=1)),
         Paragraph("不通过", ParagraphStyle('TableHeader', fontName=font_name, fontSize=10, textColor=colors.white, alignment=1)),
         Paragraph("待人工复核", ParagraphStyle('TableHeader', fontName=font_name, fontSize=10, textColor=colors.white, alignment=1))],
        [str(total_rules), str(stats['PASS']), str(stats['REJECT']), str(stats['MANUAL_CHECK'])]
    ]
    stats_table = Table(stats_data, colWidths=[40*mm, 35*mm, 35*mm, 45*mm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F3F4F6')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 8*mm))

    # Summary
    story.append(Paragraph("审查总结", heading_style))
    story.append(Paragraph(llm_summary, body_style))
    story.append(Spacer(1, 5*mm))

    # Serious problems (risk_level=高风险)
    if serious_problems:
        story.append(Paragraph("严重问题（高风险条款不通过）", heading_style))
        for i, r in enumerate(serious_problems[:8], 1):  # Limit to 8
            clause = r.get('clause_number', 'N/A')
            reason = (r.get('reasoning') or '')[:150]
            suggestion = (r.get('suggestion') or '')[:100]
            story.append(Paragraph(f"<b>{i}. 条款 {clause}</b>", small_style))
            story.append(Paragraph(f"问题：{reason}...", small_style))
            if suggestion:
                story.append(Paragraph(f"建议：{suggestion}...", small_style))
            story.append(Spacer(1, 2*mm))
        story.append(Spacer(1, 3*mm))

    # Other problems
    if medium_problems:
        story.append(Paragraph("其他问题（中/低风险条款不通过）", heading_style))
        for i, r in enumerate(medium_problems[:6], 1):  # Limit to 6
            clause = r.get('clause_number', 'N/A')
            reason = (r.get('reasoning') or '')[:100]
            story.append(Paragraph(f"{i}. 条款 {clause}：{reason}...", small_style))
        story.append(Spacer(1, 3*mm))

    # Manual check items (brief list)
    if manual_checks:
        story.append(Paragraph("待人工复核项", heading_style))
        manual_list = "、".join([r.get('clause_number', 'N/A') for r in manual_checks[:15]])
        story.append(Paragraph(f"以下条款需人工复核：{manual_list}{'...' if len(manual_checks) > 15 else ''}", small_style))

    # Build PDF
    doc.build(story)

    pdf_buffer.seek(0)
    return pdf_buffer.read()
