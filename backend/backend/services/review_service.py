from datetime import datetime, timezone
import json
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, BackgroundTasks
from sqlmodel import Session, select
from backend.core.db import engine
from backend.models.review import ReviewTask, ReviewResultItem, TaskStatus
from backend.models.document import Document, DocumentStatus
from backend.models.rule import Rule, RuleGroup
from backend.models.comparison import ComparisonDocument, ComparisonResult
from backend.schemas.review import ReviewStartRequest, ResultUpdateRequest
from backend.integrations.llm_client import generate_review_queries, compare_rule_with_context, compare_documents_chunk_wise
from backend.integrations.vector_store import search_document_chunks

async def execute_review_for_rule(
    rule: Dict[str, Any],
    document_id: str,
    document_filename: str
) -> Dict[str, Any]:
    """
    Execute review for a single rule against a document.
    Uses multi-query retrieval strategy to find actual content (not just TOC).
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

def get_all_rules_from_groups(session: Session, group_ids: List[str]) -> List[Rule]:
    """Recursively fetch rules from groups and their children."""
    rules = []
    processed_groups = set()
    
    def fetch_recursive(g_id):
        if g_id in processed_groups:
            return
        processed_groups.add(g_id)
        
        # Get rules for this group
        group_rules = session.exec(select(Rule).where(Rule.group_id == g_id)).all()
        rules.extend(group_rules)
        
        # Get children groups
        children = session.exec(select(RuleGroup).where(RuleGroup.parent_id == g_id)).all()
        for child in children:
            fetch_recursive(child.id)
            
    for gid in group_ids:
        fetch_recursive(gid)
        
    return rules

async def execute_review_background(task_id: str, document_id: str, rule_ids: List[str], comparison_doc_ids: List[str] = None):
    """Background task to execute the review process with progress updates."""
    from sqlmodel import Session as SyncSession

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
        rules = []
        for rid in rule_ids:
            r = session.get(Rule, rid)
            if r:
                rules.append(r)
        
        # Update task to PROCESSING
        task.status = TaskStatus.PROCESSING.value
        task.start_time = datetime.now(timezone.utc)
        session.commit()

        total_steps = len(rules)
        # Add steps for comparison if needed (simplified progress tracking)
        # For now, we just track rule progress. Comparison will be done after or in parallel.
        # Let's do comparison after rules.
        
        completed = 0

        print(f"[Review {task_id}] Starting review of {len(rules)} rules against document '{doc.filename}'")

        # 1. Execute Rule Review
        for i, rule in enumerate(rules):
            # Check for cancellation
            session.refresh(task)
            if task.status == TaskStatus.CANCELLED.value:
                print(f"[Review {task_id}] Review cancelled by user.")
                return

            try:
                print(f"[Review {task_id}] Processing rule {i+1}/{len(rules)}: {rule.clause_number}")

                # Execute review for this rule
                rule_dict = {
                    "id": rule.id,
                    "content": rule.content,
                    "clause_number": rule.clause_number,
                    "review_type": rule.review_type,
                    "risk_level": rule.risk_level
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
                task.progress = int((completed / total_steps) * 100)
                session.commit()

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
                task.progress = int((completed / total_steps) * 100)
                session.commit()

        # 2. Execute Comparison Review (if any)
        if comparison_doc_ids:
            print(f"[Review {task_id}] Starting comparison with {len(comparison_doc_ids)} documents")
            # For each comparison document
            for comp_id in comparison_doc_ids:
                comp_doc = session.get(ComparisonDocument, comp_id)
                if not comp_doc:
                    continue
                
                try:
                    # We need to iterate through chunks of the REVIEW document
                    # and compare them with the COMPARISON document.
                    # This is expensive. We should probably sample or use a smarter strategy.
                    # For now, let's take the first 20 chunks of the review document as a prototype.
                    from backend.models.chunk import DocumentChunk
                    review_chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == document_id).limit(20)).all()
                    
                    conflicts = []
                    
                    for chunk in review_chunks:
                        # Search for relevant chunks in comparison document
                        # We need to search in the vector store using the comparison doc ID
                        # But wait, ingest_chunks_to_chroma uses 'document_id' as metadata.
                        # So we can search using filter={"document_id": comp_id}
                        
                        relevant_comp_chunks = await search_document_chunks(
                            query=chunk.content,
                            document_id=comp_id,
                            n_results=3
                        )
                        
                        if not relevant_comp_chunks:
                            continue
                            
                        # Compare using LLM
                        comp_result = await compare_documents_chunk_wise(
                            target_chunk=chunk.content,
                            reference_chunks=relevant_comp_chunks,
                            target_filename=doc.filename,
                            reference_filename=comp_doc.filename
                        )
                        
                        if comp_result["result_code"] == "CONFLICT":
                            conflicts.append({
                                "chunk_index": chunk.chunk_index,
                                "target_content": chunk.content[:100] + "...",
                                "reasoning": comp_result["reasoning"],
                                "evidence": comp_result["evidence"],
                                "suggestion": comp_result["suggestion"]
                            })
                            
                    # Save ComparisonResult
                    comparison_result = ComparisonResult(
                        task_id=task_id,
                        comparison_document_id=comp_id,
                        conflict_score=len(conflicts) / len(review_chunks) if review_chunks else 0.0,
                        summary=f"Found {len(conflicts)} potential conflicts in sampled chunks.",
                        details=json.dumps(conflicts, ensure_ascii=False)
                    )
                    session.add(comparison_result)
                    session.commit()
                    
                except Exception as e:
                    print(f"[Review {task_id}] Error comparing with {comp_doc.filename}: {e}")

        # Mark task as completed
        task.status = TaskStatus.COMPLETED.value
        task.progress = 100
        task.end_time = datetime.now(timezone.utc)
        session.commit()

        print(f"[Review {task_id}] Review completed!")

class ReviewService:
    @staticmethod
    def get_reviews(session: Session) -> List[Dict]:
        """Get all review tasks with document and rule group info."""
        tasks = session.exec(
            select(ReviewTask).order_by(ReviewTask.created_at.desc())
        ).all()

        # Enrich with document and rule group names
        enriched = []
        for task in tasks:
            doc = session.get(Document, task.document_id)
            # Fetch group name if available, or use stored names
            group_name = "Unknown"
            if task.rule_group_names:
                group_name = task.rule_group_names
            elif task.rule_group_id:
                group = session.get(RuleGroup, task.rule_group_id)
                group_name = group.name if group else "Unknown"
                
            enriched.append({
                "id": task.id,
                "document_id": task.document_id,
                "document_name": doc.filename if doc else "Unknown",
                "rule_group_id": task.rule_group_id,
                "rule_group_name": group_name,
                "rule_group_names": task.rule_group_names,
                "status": task.status,
                "progress": task.progress,
                "start_time": task.start_time.isoformat() if task.start_time else None,
                "end_time": task.end_time.isoformat() if task.end_time else None,
                "created_at": task.created_at.isoformat()
            })

        return enriched

    @staticmethod
    async def start_review(
        session: Session,
        data: ReviewStartRequest,
        background_tasks: BackgroundTasks
    ) -> Dict:
        """Start a new review task."""
        # Validate document exists and is processed
        doc = session.get(Document, data.document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.status != DocumentStatus.DONE.value:
            raise HTTPException(status_code=400, detail=f"Document is not processed yet. Current status: {doc.status}")

        # Validate inputs
        if not data.rule_group_ids and not data.comparison_document_ids:
             raise HTTPException(status_code=400, detail="No rule groups or comparison documents selected")
             
        # Fetch all rules recursively if groups selected
        rules = []
        if data.rule_group_ids:
            rules = get_all_rules_from_groups(session, data.rule_group_ids)
            if not rules and not data.comparison_document_ids:
                raise HTTPException(status_code=400, detail="Selected groups have no rules")

        # Get group names for display
        group_names = []
        if data.rule_group_ids:
            for gid in data.rule_group_ids:
                g = session.get(RuleGroup, gid)
                if g:
                    group_names.append(g.name)
        
        # Create task
        task = ReviewTask(
            document_id=data.document_id,
            rule_group_id=data.rule_group_ids[0] if data.rule_group_ids else None, # Store first one as primary reference
            rule_group_names=", ".join(group_names),
            comparison_document_ids=",".join(data.comparison_document_ids) if data.comparison_document_ids else None,
            status=TaskStatus.PENDING.value,
            progress=0
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        # Start background execution
        rule_ids = [r.id for r in rules]
        
        background_tasks.add_task(
            execute_review_background,
            task.id,
            data.document_id,
            rule_ids,
            data.comparison_document_ids
        )

        return {
            "task_id": task.id,
            "status": task.status,
            "message": f"Review started for document '{doc.filename}'",
            "total_rules": len(rules)
        }

    @staticmethod
    def get_review_task(session: Session, task_id: str) -> Dict:
        """Get review task status with details."""
        task = session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        doc = session.get(Document, task.document_id)
        
        group_name = "Unknown"
        if task.rule_group_names:
            group_name = task.rule_group_names
        elif task.rule_group_id:
            group = session.get(RuleGroup, task.rule_group_id)
            group_name = group.name if group else "Unknown"

        # Count results by type
        results = session.exec(
            select(ReviewResultItem).where(ReviewResultItem.task_id == task_id)
        ).all()

        stats = {"PASS": 0, "REJECT": 0, "MANUAL_CHECK": 0}
        for r in results:
            if r.result_code in stats:
                stats[r.result_code] += 1
                
        # Get comparison results
        comp_results = session.exec(
            select(ComparisonResult).where(ComparisonResult.task_id == task_id)
        ).all()
        
        comp_stats = []
        for cr in comp_results:
            comp_doc = session.get(ComparisonDocument, cr.comparison_document_id)
            comp_stats.append({
                "document_name": comp_doc.filename if comp_doc else "Unknown",
                "conflict_score": cr.conflict_score,
                "summary": cr.summary
            })

        return {
            "id": task.id,
            "document_id": task.document_id,
            "document_name": doc.filename if doc else "Unknown",
            "rule_group_id": task.rule_group_id,
            "rule_group_name": group_name,
            "rule_group_names": task.rule_group_names,
            "status": task.status,
            "progress": task.progress,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "end_time": task.end_time.isoformat() if task.end_time else None,
            "created_at": task.created_at.isoformat(),
            "results_count": len(results),
            "stats": stats,
            "comparison_stats": comp_stats
        }

    @staticmethod
    def get_review_results(session: Session, task_id: str) -> List[Dict]:
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
                "risk_level": rule.risk_level if rule else "中风险",
                "result_code": result.result_code,
                "reasoning": result.reasoning,
                "evidence": result.evidence,
                "suggestion": result.suggestion,
                "created_at": result.created_at.isoformat()
            })

        return enriched

    @staticmethod
    def delete_review_task(session: Session, task_id: str) -> Dict:
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
            
        # Delete comparison results
        comp_results = session.exec(
            select(ComparisonResult).where(ComparisonResult.task_id == task_id)
        ).all()
        for cr in comp_results:
            session.delete(cr)

        # Delete task
        session.delete(task)
        session.commit()

        return {"message": f"Review task and results deleted"}

    @staticmethod
    def cancel_review_task(session: Session, task_id: str) -> Dict:
        """Cancel a running review task."""
        task = session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status not in [TaskStatus.PENDING.value, TaskStatus.PROCESSING.value]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel task in {task.status} state")

        task.status = TaskStatus.CANCELLED.value
        task.end_time = datetime.now(timezone.utc)
        session.add(task)
        session.commit()

        return {"message": "Review task cancelled", "status": task.status}

    @staticmethod
    def get_review_result(session: Session, result_id: str) -> Dict:
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
            "risk_level": rule.risk_level if rule else "中风险",
            "result_code": result.result_code,
            "reasoning": result.reasoning,
            "evidence": result.evidence,
            "suggestion": result.suggestion,
            "created_at": result.created_at.isoformat()
        }

    @staticmethod
    def update_review_result(session: Session, result_id: str, data: ResultUpdateRequest) -> Dict:
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

    @staticmethod
    def delete_review_result(session: Session, result_id: str) -> Dict:
        """Delete a single review result item."""
        result = session.get(ReviewResultItem, result_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")

        session.delete(result)
        session.commit()
        return {"message": "Result deleted successfully"}