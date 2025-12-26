import os
import json
from typing import List, Dict, Any
from fastapi import UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from backend.core.config import settings
from backend.core.db import engine
from backend.models.analysis import HistoryAnalysisTask, InferredOpinion, AnalysisStatus, OpinionStatus
from backend.models.rule import Rule, RuleGroup
from backend.schemas.analysis import OpinionUpdate, ConvertToRuleRequest
from backend.services.document_service import extract_text_from_file
from backend.integrations.llm_client import compare_documents_and_extract_opinions

async def run_analysis_background(
    task_id: str,
    draft_texts: List[str],
    approved_texts: List[str],
    draft_names: List[str],
    approved_names: List[str]
):
    from sqlmodel import Session as SyncSession

    with SyncSession(engine) as session:
        task = session.get(HistoryAnalysisTask, task_id)
        if not task:
            return

        try:
            opinions = await compare_documents_and_extract_opinions(
                draft_texts, approved_texts, draft_names, approved_names
            )

            for op in opinions:
                opinion_obj = InferredOpinion(
                    task_id=task_id,
                    opinion=op.get("opinion", ""),
                    evidence=op.get("evidence", ""),
                    clause=op.get("clause", ""),
                    risk_level=op.get("risk_level", "中风险"),
                    status=OpinionStatus.PENDING.value
                )
                session.add(opinion_obj)

            task.status = AnalysisStatus.COMPLETED.value
            session.commit()

        except Exception as e:
            print(f"Analysis failed: {e}")
            task.status = AnalysisStatus.FAILED.value
            session.commit()

class AnalysisService:
    @staticmethod
    async def start_history_analysis(
        session: Session,
        draft_files: List[UploadFile],
        approved_files: List[UploadFile],
        background_tasks: BackgroundTasks
    ) -> HistoryAnalysisTask:
        """Start a new history analysis task."""
        # Create analysis uploads directory
        ANALYSIS_UPLOADS_DIR = os.path.join(settings.UPLOADS_DIR, "analysis")
        os.makedirs(ANALYSIS_UPLOADS_DIR, exist_ok=True)

        # 1. Create Task first to get task_id
        task = HistoryAnalysisTask(
            draft_filenames=json.dumps([f.filename for f in draft_files]),
            approved_filenames=json.dumps([f.filename for f in approved_files]),
            status=AnalysisStatus.PROCESSING.value
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        # 2. Save files to disk and read contents
        task_dir = os.path.join(ANALYSIS_UPLOADS_DIR, task.id)
        os.makedirs(task_dir, exist_ok=True)

        draft_contents = []
        draft_names = []
        draft_paths = []

        for idx, f in enumerate(draft_files):
            await f.seek(0)
            content = await f.read()

            # Save to disk
            filename = f.filename or f"draft_{idx}"
            file_path = os.path.join(task_dir, f"draft_{idx}_{filename}")
            with open(file_path, 'wb') as disk_file:
                disk_file.write(content)
            draft_paths.append(file_path)

            # Extract text
            text = await extract_text_from_file(content, filename)
            draft_contents.append(text)
            draft_names.append(filename)

        approved_contents = []
        approved_names = []
        approved_paths = []

        for idx, f in enumerate(approved_files):
            await f.seek(0)
            content = await f.read()

            # Save to disk
            filename = f.filename or f"approved_{idx}"
            file_path = os.path.join(task_dir, f"approved_{idx}_{filename}")
            with open(file_path, 'wb') as disk_file:
                disk_file.write(content)
            approved_paths.append(file_path)

            # Extract text
            text = await extract_text_from_file(content, filename)
            approved_contents.append(text)
            approved_names.append(filename)

        # 3. Update task with file paths
        task.draft_file_paths = json.dumps(draft_paths)
        task.approved_file_paths = json.dumps(approved_paths)
        session.add(task)
        session.commit()

        # 4. Start Background Analysis
        background_tasks.add_task(
            run_analysis_background,
            task.id,
            draft_contents,
            approved_contents,
            draft_names,
            approved_names
        )

        return task

    @staticmethod
    def get_history_analysis(session: Session, task_id: str) -> Dict:
        """Get analysis task and its opinions."""
        task = session.get(HistoryAnalysisTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        opinions = session.exec(select(InferredOpinion).where(InferredOpinion.task_id == task_id)).all()

        return {
            "task": task,
            "opinions": opinions
        }

    @staticmethod
    def update_opinion(session: Session, opinion_id: str, data: OpinionUpdate) -> InferredOpinion:
        """Update an inferred opinion."""
        op = session.get(InferredOpinion, opinion_id)
        if not op:
            raise HTTPException(status_code=404, detail="Opinion not found")

        if data.opinion is not None:
            op.opinion = data.opinion
        if data.risk_level is not None:
            op.risk_level = data.risk_level
        if data.review_type is not None:
            op.review_type = data.review_type

        session.add(op)
        session.commit()
        session.refresh(op)
        return op

    @staticmethod
    def delete_opinion(session: Session, opinion_id: str) -> Dict:
        """Soft delete an opinion."""
        op = session.get(InferredOpinion, opinion_id)
        if not op:
            raise HTTPException(status_code=404, detail="Opinion not found")

        op.status = OpinionStatus.DELETED.value
        session.add(op)
        session.commit()
        return {"message": "Opinion deleted"}

    @staticmethod
    def get_analysis_file(session: Session, task_id: str, file_type: str, file_index: int) -> FileResponse:
        """Serve stored analysis files."""
        task = session.get(HistoryAnalysisTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Get file paths
        if file_type == "draft":
            paths = json.loads(task.draft_file_paths)
        elif file_type == "approved":
            paths = json.loads(task.approved_file_paths)
        else:
            raise HTTPException(status_code=400, detail="file_type must be 'draft' or 'approved'")

        if file_index < 0 or file_index >= len(paths):
            raise HTTPException(status_code=404, detail="File index out of range")

        file_path = paths[file_index]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")

        # Determine media type
        if file_path.lower().endswith('.pdf'):
            media_type = 'application/pdf'
        elif file_path.lower().endswith(('.docx', '.doc')):
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            media_type = 'application/octet-stream'

        return FileResponse(file_path, media_type=media_type)

    @staticmethod
    def convert_opinion_to_rule(session: Session, opinion_id: str, data: ConvertToRuleRequest) -> List[Rule]:
        """Convert an opinion to a rule in the specified groups."""
        op = session.get(InferredOpinion, opinion_id)
        if not op:
            raise HTTPException(status_code=404, detail="Opinion not found")

        created_rules = []
        for group_id in data.rule_group_ids:
            group = session.get(RuleGroup, group_id)
            if not group:
                continue # Skip invalid groups or raise error? Let's skip for robustness

            # Create Rule
            rule = Rule(
                group_id=group_id,
                clause_number=op.clause or "N/A",
                content=op.opinion,
                review_type=op.review_type or "内容完整性",  # Use opinion's review_type or default
                risk_level=op.risk_level
            )
            session.add(rule)
            created_rules.append(rule)

        # Update Opinion Status
        op.status = OpinionStatus.ADDED.value
        session.add(op)

        session.commit()
        for r in created_rules:
            session.refresh(r)
            
        return created_rules