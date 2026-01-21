from typing import Generator, Any, Dict
import uuid
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from backend.core.db import engine
from backend.core.config import settings
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

    # Fetch User Profile from Supabase directly via REST API (Foolproof Auth)
    try:
        # Use httpx to make a request with the user's token to ensure RLS context
        # Supabase Python client auth state can be tricky, raw HTTP is safer here.
        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        url = f"{settings.SUPABASE_URL}/rest/v1/profiles"
        params = {"id": f"eq.{user.id}", "select": "*"}
        
        with httpx.Client() as client:
            resp = client.get(url, headers=headers, params=params)
            
        if resp.status_code != 200:
             # If RLS denies, it might return 200 with empty list, or 401/403
             # If API key wrong: 401
             print(f"DEBUG: Supabase API Error {resp.status_code}: {resp.text}")
             # Raise exception to trigger the fallback in the except block
             raise Exception(f"Supabase API Error {resp.status_code}: {resp.text}")

        data = resp.json()
        profile_data: Any = data[0] if data else None

        if profile_data is None:
            # Auto-create profile in Supabase if missing
            new_profile = {
                "id": user.id,
                "email": user.email,
                "subscription_credits": 10,
                "topup_credits": 0
            }
            with httpx.Client() as client:
                 resp_ins = client.post(url, headers=headers, json=new_profile)
            
            if resp_ins.status_code in (200, 201):
                 ins_data = resp_ins.json()
                 profile_data = ins_data[0] if ins_data else new_profile
            else:
                 # If insert fails, maybe it exists but invisible? Or permission denied.
                 # Fallback to defaults to prevent 500 error, ensuring user can at least load profile.
                 print(f"DEBUG: Failed to auto-create profile: {resp_ins.text}")
                 profile_data = new_profile

        # Map to Profile model
        profile = Profile(
            id=uuid.UUID(str(profile_data['id'])),
            email=str(profile_data.get('email', '')) if profile_data.get('email') else None,
            subscription_credits=int(profile_data.get('subscription_credits', 0)),
            topup_credits=int(profile_data.get('topup_credits', 0))
        )
        return profile
        
    except Exception as e:
        import traceback
        print(f"DEBUG: Supabase Profile Fetch Error: {str(e)}")
        print(traceback.format_exc())
        
        # Fallback to a basic profile so the user can still use core features
        # This prevents blocking the entire app if the external profile service is down or misconfigured (RLS recursion)
        print("DEBUG: Falling back to local default profile")
        fallback_profile = Profile(
            id=uuid.UUID(str(user.id)),
            email=str(user.email) if user.email else None,
            subscription_credits=0, # Default to 0 credits on fallback
            topup_credits=0
        )
        return fallback_profile