from fastapi import APIRouter, Depends
from backend.api.deps import get_current_user
from backend.models.user import Profile

router = APIRouter()

@router.get("/users/me")
def read_users_me(current_user: Profile = Depends(get_current_user)):
    return current_user