import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.user import Profile
from backend.api.deps import get_current_user
from backend.core.config import settings

# --- Integration Test for Endpoint ---

def test_read_users_me_endpoint(client: TestClient):
    """
    Test GET /api/v1/users/me
    Verifies that the endpoint correctly returns the user profile
    provided by the dependency.
    """
    # Create a mock user profile
    user_id = uuid.uuid4()
    mock_profile = Profile(
        id=user_id,
        email="test@example.com",
        subscription_credits=50,
        topup_credits=10
    )

    # Override the dependency
    app.dependency_overrides[get_current_user] = lambda: mock_profile

    response = client.get("/api/v1/users/me")
    
    # Clean up override
    app.dependency_overrides = {}

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["subscription_credits"] == 50
    assert data["topup_credits"] == 10
    assert data["credits"] == 60  # Check the property computed field


# --- Unit Tests for Dependency Logic ---

@patch("backend.api.deps.get_supabase_client")
@patch("backend.api.deps.httpx.Client")
def test_get_current_user_success(mock_httpx_cls, mock_get_supabase_client):
    """
    Test get_current_user dependency logic when Supabase returns valid data.
    """
    # 1. Mock Supabase Auth User
    mock_user_id = str(uuid.uuid4())
    mock_user = MagicMock()
    mock_user.id = mock_user_id
    mock_user.email = "real@example.com"
    
    mock_supabase = MagicMock()
    mock_supabase.auth.get_user.return_value.user = mock_user
    mock_get_supabase_client.return_value = mock_supabase

    # 2. Mock HTTPX response for Profile fetch
    mock_client_instance = mock_httpx_cls.return_value.__enter__.return_value
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Return a list containing the profile (Supabase REST API format)
    mock_response.json.return_value = [{
        "id": mock_user_id,
        "email": "real@example.com",
        "subscription_credits": 100,
        "topup_credits": 20
    }]
    mock_client_instance.get.return_value = mock_response

    # Call the function
    # We pass a dummy token and session (can be None since we mocked internals)
    result_profile = get_current_user(token="valid_token", session=None)

    # Assertions
    assert result_profile.email == "real@example.com"
    assert result_profile.subscription_credits == 100
    assert result_profile.topup_credits == 20
    assert result_profile.credits == 120 # Total credits property

    # Verify that we are filtering by User ID now!
    # This prevents IDOR or fetching the wrong user if RLS returns multiple rows
    mock_client_instance.get.assert_called()
    call_args = mock_client_instance.get.call_args
    # call_args[1] is kwargs
    assert "params" in call_args[1]
    assert call_args[1]["params"].get("id") == f"eq.{mock_user_id}"


@patch("backend.api.deps.get_supabase_client")
@patch("backend.api.deps.httpx.Client")
def test_get_current_user_profile_not_found(mock_httpx_cls, mock_get_supabase_client):
    """
    Test valid auth but empty profile (first time login), should auto-create or return default.
    """
    # 1. Mock Supabase Auth User
    mock_user_id = str(uuid.uuid4())
    mock_user = MagicMock()
    mock_user.id = mock_user_id
    mock_user.email = "newuser@example.com"
    
    mock_supabase = MagicMock()
    mock_supabase.auth.get_user.return_value.user = mock_user
    mock_get_supabase_client.return_value = mock_supabase

    # 2. Mock HTTPX response for Profile fetch -> Empty List (Not Found)
    mock_client_instance = mock_httpx_cls.return_value.__enter__.return_value
    
    # First call (GET) returns empty list
    get_response = MagicMock()
    get_response.status_code = 200
    get_response.json.return_value = []
    
    # Second call (POST) to create profile returns success
    post_response = MagicMock()
    post_response.status_code = 201
    post_response.json.return_value = [{
        "id": mock_user_id,
        "email": "newuser@example.com",
        "subscription_credits": 10, # Default logic in deps.py
        "topup_credits": 0
    }]
    
    # Configure side_effect for different calls or handle specifically
    # In deps.py: GET is first, POST is second if GET is empty
    mock_client_instance.get.return_value = get_response
    mock_client_instance.post.return_value = post_response

    # Call
    result_profile = get_current_user(token="valid_token", session=None)

    # Assertions
    assert result_profile.email == "newuser@example.com"
    assert result_profile.subscription_credits == 10 # Should match default creation logic
    
    # Verify POST was called to create profile
    mock_client_instance.post.assert_called_once()


@patch("backend.api.deps.get_supabase_client")
@patch("backend.api.deps.httpx.Client")
def test_get_current_user_api_failure_fallback(mock_httpx_cls, mock_get_supabase_client):
    """
    Test when Supabase/HTTPX fails completely (e.g. 500 error), should return fallback profile.
    """
    # 1. Mock Supabase Auth User (Auth still needs to pass for us to know WHO it is)
    mock_user_id = str(uuid.uuid4())
    mock_user = MagicMock()
    mock_user.id = mock_user_id
    mock_user.email = "error@example.com"
    
    mock_supabase = MagicMock()
    mock_supabase.auth.get_user.return_value.user = mock_user
    mock_get_supabase_client.return_value = mock_supabase

    # 2. Mock HTTPX response to Raise Exception
    mock_client_instance = mock_httpx_cls.return_value.__enter__.return_value
    mock_client_instance.get.side_effect = Exception("Connection Refused")

    # Call
    result_profile = get_current_user(token="valid_token", session=None)

    # Assertions - Should return fallback
    assert result_profile.email == "error@example.com"
    assert result_profile.subscription_credits == 0 # Fallback default
    assert result_profile.topup_credits == 0


@patch("backend.api.deps.get_supabase_client")
@patch("backend.api.deps.httpx.Client")
def test_get_current_user_null_fields(mock_httpx_cls, mock_get_supabase_client):
    """
    Test when Supabase returns a profile with NULL (None) fields.
    Current implementation might fail here.
    """
    # 1. Mock Supabase Auth User
    mock_user_id = str(uuid.uuid4())
    mock_user = MagicMock()
    mock_user.id = mock_user_id
    mock_user.email = "nuller@example.com"
    
    mock_supabase = MagicMock()
    mock_supabase.auth.get_user.return_value.user = mock_user
    mock_get_supabase_client.return_value = mock_supabase

    # 2. Mock HTTPX response -> Returns profile but with None values
    mock_client_instance = mock_httpx_cls.return_value.__enter__.return_value
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{
        "id": mock_user_id,
        "email": "nuller@example.com",
        "subscription_credits": None, # Simulating Database Null
        "topup_credits": None         # Simulating Database Null
    }]
    mock_client_instance.get.return_value = mock_response

    # Call
    try:
        result_profile = get_current_user(token="valid_token", session=None)
        
        # If it doesn't raise exception, we check if it handled None -> 0
        assert result_profile.subscription_credits == 0
        assert result_profile.topup_credits == 0
        
    except Exception as e:
        # If the code crashes inside (TypeError: int() argument must be string...),
        # it catches Exception and returns Fallback (credits=0).
        # So arguably, the user still sees 0. 
        # But we want to confirm if it crashes or parses correctly.
        # If it crashed, we want to FIX it so we don't rely on fallback.
        pass
        # To strictly verify it didn't crash, we'd check logs or behavior.
        # But here, we just want to ensure result is robust.
        assert result_profile.subscription_credits == 0