import pytest
import uuid
from sqlmodel import Session, select
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.rule import RuleGroup
from backend.models.user import Profile

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides = {} 
    from backend.api.deps import get_session
    app.dependency_overrides[get_session] = get_session_override
    
    return TestClient(app)

def test_rule_group_edit_permission(client: TestClient, session: Session):
    # Setup users
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    
    user_a = Profile(id=user_a_id, email="a@example.com")
    user_b = Profile(id=user_b_id, email="b@example.com")
    session.add(user_a)
    session.add(user_b)
    session.commit()
    
    # Setup override for current_user
    from backend.api.deps import get_current_user
    
    # 1. User A creates groups
    app.dependency_overrides[get_current_user] = lambda: user_a
    
    # Create Private Group
    resp = client.post("/api/v1/rule-groups", json={"name": "A Private", "type": "private"})
    assert resp.status_code == 200, resp.text
    private_group_id = resp.json()["id"]
    
    # Create Public Group
    resp = client.post("/api/v1/rule-groups", json={"name": "A Public", "type": "public"})
    assert resp.status_code == 200, resp.text
    public_group_id = resp.json()["id"]
    
    # Check that User A can see both
    resp = client.get("/api/v1/rule-groups")
    ids = [g["id"] for g in resp.json()]
    assert private_group_id in ids
    assert public_group_id in ids

    # 2. User B tries to access/edit
    app.dependency_overrides[get_current_user] = lambda: user_b
    
    # Get all groups (should see Public, shouldn't see Private)
    resp = client.get("/api/v1/rule-groups")
    assert resp.status_code == 200
    groups = resp.json()
    ids = [g["id"] for g in groups]
    assert public_group_id in ids
    assert private_group_id not in ids
    
    # Try to edit Private Group (should succeed 404 or fail 403?)
    # Since get_rule_group does NOT check permissions (it just returns if found),
    # User B *could* technically fetch the group details if they knew the ID?
    # Let's check get_rule_group
    resp = client.get(f"/api/v1/rule-groups/{private_group_id}")
    # Ideally this should be 403 or filtered. 
    # Current implementation: Only get_rule_groups (list) filters. 
    # get_rule_group (single) does NOT filter! 
    # This might be a security issue, enabling User B to at least SEE the private group metadata if they guess the ID.
    # But let's check UPDATE.
    
    resp = client.put(f"/api/v1/rule-groups/{private_group_id}", json={"name": "B Hacked", "type": "public"})
    # Expect 403 because User B is not owner and it's private.
    assert resp.status_code == 403
    
    # Try to edit Public Group (should succeed based on "edit what you see")
    resp = client.put(f"/api/v1/rule-groups/{public_group_id}", json={"name": "B Edited Public", "type": "public"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "B Edited Public"
    
    # Try to change Public Group to Private (should succeed)
    # This effectively "steals" the group visibility from public to User B? 
    # No, owner is still User A. User B just hides it from everyone else (including himself, if he's not owner).
    resp = client.put(f"/api/v1/rule-groups/{public_group_id}", json={"name": "B Made Private", "type": "private"})
    assert resp.status_code == 200
    assert resp.json()["type"] == "private"
    
    # Now verify User A still sees it (since they are owner)
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.get(f"/api/v1/rule-groups/{public_group_id}")
    assert resp.status_code == 200
    assert resp.json()["type"] == "private"
    
    # User B should NOT see it anymore in list
    app.dependency_overrides[get_current_user] = lambda: user_b
    resp = client.get("/api/v1/rule-groups")
    ids = [g["id"] for g in resp.json()]
    assert public_group_id not in ids

    # Cleanup
    app.dependency_overrides = {}