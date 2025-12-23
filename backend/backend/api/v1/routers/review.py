from typing import List, Dict
from fastapi import APIRouter, Depends, BackgroundTasks, Response
from sqlmodel import Session
from backend.api.deps import get_session
from backend.schemas.review import ReviewStartRequest, ResultUpdateRequest
from backend.services.review_service import ReviewService
from backend.services.report_service import ReportService

router = APIRouter()

@router.get("/reviews")
def get_reviews(session: Session = Depends(get_session)):
    """Get all review tasks with document and rule group info."""
    return ReviewService.get_reviews(session)

@router.post("/reviews/start")
async def start_review(
    data: ReviewStartRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Start a new review task."""
    return await ReviewService.start_review(session, data, background_tasks)

@router.get("/reviews/{task_id}")
def get_review_task(task_id: str, session: Session = Depends(get_session)):
    """Get review task status with details."""
    return ReviewService.get_review_task(session, task_id)

@router.get("/reviews/{task_id}/results")
def get_review_results(task_id: str, session: Session = Depends(get_session)):
    """Get review results for a task with rule details."""
    return ReviewService.get_review_results(session, task_id)

@router.delete("/reviews/{task_id}")
def delete_review_task(task_id: str, session: Session = Depends(get_session)):
    """Delete a review task and its results."""
    return ReviewService.delete_review_task(session, task_id)

@router.post("/reviews/{task_id}/cancel")
def cancel_review_task(task_id: str, session: Session = Depends(get_session)):
    """Cancel a running review task."""
    return ReviewService.cancel_review_task(session, task_id)

@router.get("/results/{result_id}")
def get_review_result(result_id: str, session: Session = Depends(get_session)):
    """Get a single review result item with rule details."""
    return ReviewService.get_review_result(session, result_id)

@router.put("/results/{result_id}")
def update_review_result(result_id: str, data: ResultUpdateRequest, session: Session = Depends(get_session)):
    """Update a review result item."""
    return ReviewService.update_review_result(session, result_id, data)

@router.delete("/results/{result_id}")
def delete_review_result(result_id: str, session: Session = Depends(get_session)):
    """Delete a single review result item."""
    return ReviewService.delete_review_result(session, result_id)

@router.get("/reviews/{task_id}/summary-pdf")
async def generate_summary_pdf(task_id: str, session: Session = Depends(get_session)):
    """Generate a summary PDF report for a review task (max 2 pages)."""
    return await ReportService.generate_summary_pdf(session, task_id)