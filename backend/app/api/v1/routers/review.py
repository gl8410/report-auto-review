from typing import List, Dict
from fastapi import APIRouter, Depends, BackgroundTasks, Response, HTTPException, status
from sqlmodel import Session
from app.api.deps import get_session, get_current_user
from app.schemas.review import ReviewStartRequest, ResultUpdateRequest, ReviewCostRequest
from app.services.review_service import ReviewService
from app.models.user import Profile
from app.services.report_service import ReportService

router = APIRouter()

@router.get("/reviews")
def get_reviews(session: Session = Depends(get_session), current_user: Profile = Depends(get_current_user)):
    """Get all review tasks with document and rule group info."""
    return ReviewService.get_reviews(session, str(current_user.id))
@router.post("/reviews/cost")
def estimate_review_cost(
    data: ReviewCostRequest,
    session: Session = Depends(get_session)
):
    """Calculate the estimated cost (credit amount) for a review."""
    rule_checks = ReviewService.calculate_cost(session, data.rule_group_ids)
    
    # Currently comparison docs are not charged or charged separately?
    # Based on start_review implementation, only rules are charged.
    comparison_checks = len(data.comparison_document_ids) if data.comparison_document_ids else 0
    # Note: Currently logic charges only for rules. Comparison items are just listed.
    
    return {
        "total_cost": rule_checks,
        "breakdown": {
            "rule_checks": rule_checks,
            "comparison_checks": comparison_checks
        },
        "currency": "credits"
    }

@router.post("/reviews/start")
async def start_review(
    data: ReviewStartRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: Profile = Depends(get_current_user)
):
    """Start a new review task."""
    # Logic for credit deduction is now inside ReviewService.start_review to ensure atomic operation with logic
    return await ReviewService.start_review(session, data, background_tasks, str(current_user.id))

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
async def cancel_review_task(task_id: str, session: Session = Depends(get_session)):
    """Cancel a running review task."""
    return await ReviewService.cancel_review_task(session, task_id)

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