from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks
from sqlmodel import Session
from app.api.deps import get_session
from app.schemas.analysis import OpinionUpdate, ConvertToRuleRequest
from app.services.analysis_service import AnalysisService

router = APIRouter()

@router.post("/history-analysis")
async def start_history_analysis(
    draft_files: List[UploadFile] = File(...),
    approved_files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session)
):
    """Start a new history analysis task."""
    return await AnalysisService.start_history_analysis(session, draft_files, approved_files, background_tasks)

@router.get("/history-analysis/{task_id}")
def get_history_analysis(task_id: str, session: Session = Depends(get_session)):
    """Get analysis task and its opinions."""
    return AnalysisService.get_history_analysis(session, task_id)

@router.put("/history-analysis/opinions/{opinion_id}")
def update_opinion(opinion_id: str, data: OpinionUpdate, session: Session = Depends(get_session)):
    """Update an inferred opinion."""
    return AnalysisService.update_opinion(session, opinion_id, data)

@router.delete("/history-analysis/opinions/{opinion_id}")
def delete_opinion(opinion_id: str, session: Session = Depends(get_session)):
    """Soft delete an opinion."""
    return AnalysisService.delete_opinion(session, opinion_id)

@router.get("/history-analysis/files/{task_id}/{file_type}/{file_index}")
async def get_analysis_file(
    task_id: str,
    file_type: str,
    file_index: int,
    session: Session = Depends(get_session)
):
    """Serve stored analysis files."""
    return AnalysisService.get_analysis_file(session, task_id, file_type, file_index)

@router.post("/history-analysis/opinions/{opinion_id}/convert")
def convert_opinion_to_rule(
    opinion_id: str,
    data: ConvertToRuleRequest,
    session: Session = Depends(get_session)
):
    """Convert an opinion to rules in the specified groups."""
    return AnalysisService.convert_opinion_to_rule(session, opinion_id, data)