from fastapi import APIRouter
from backend.api.v1.routers import rule, document, review, analysis, comparison


api_router = APIRouter()

api_router.include_router(rule.router, tags=["rules"])
api_router.include_router(document.router, tags=["documents"])
api_router.include_router(review.router, tags=["reviews"])
api_router.include_router(analysis.router, tags=["analysis"])
api_router.include_router(comparison.router, tags=["comparison"])