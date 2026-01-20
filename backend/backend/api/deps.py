from typing import Generator
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from backend.core.db import engine
from backend.core.supabase import get_supabase_client
from backend.models.user import Profile

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def get_session() -> Generator[Session, None, None]:
    """Get database session."""
    with Session(engine) as session:
        yield session

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> Profile:
    """
    Validates the bearer token using Supabase and returns the user profile.
    If profile doesn't exist but token is valid, creates a default profile.
    """
    if not token:
        # Check if we are in a dev environment/legacy mode without auth? 
        # No, strict auth as per plan.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase = get_supabase_client()
    
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = user_response.user
        
    except Exception as e:
        # Supabase client might raise different exceptions
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch User Profile from DB
    profile = session.get(Profile, uuid.UUID(user.id))
    
    if not profile:
        # Auto-create profile if missing (fallback for manual user creation or failed triggers)
        try:
            profile = Profile(
                 id=uuid.UUID(user.id),
                 email=user.email,
                 credits=10
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
        except Exception as e:
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create user profile: {str(e)}",
            )
            
    return profile