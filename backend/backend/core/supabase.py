from supabase import create_client, Client
from backend.core.config import settings

def get_supabase_client(use_service_role: bool = False) -> Client:
    """
    Get Supabase client.
    
    Args:
        use_service_role: If True, uses service role key (for admin operations).
                         If False, uses anon key (for user operations).
    """
    if not settings.SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL must be set in .env")
        
    if use_service_role:
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    else:
        if not settings.SUPABASE_KEY:
            raise RuntimeError("SUPABASE_KEY must be set in .env")
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)