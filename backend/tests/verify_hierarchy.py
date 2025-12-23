import requests
import json
import time

API_BASE = "http://localhost:8000/api/v1"

def log(msg):
    print(msg)
    with open("verification_result.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def test_hierarchy():
    # Clear previous log
    with open("verification_result.txt", "w", encoding="utf-8") as f:
        f.write("Starting Verification...\n")

    log("1. Creating Parent Group...")
    try:
        res = requests.post(f"{API_BASE}/rule-groups", json={"name": "Parent Group", "description": "Top level"})
    except Exception as e:
        log(f"Request failed: {e}")
        return

    if res.status_code != 200:
        log(f"Failed to create parent: {res.text}")
        return
    parent = res.json()
    log(f"   Parent created: {parent['id']}")

    log("2. Creating Child Group...")
    res = requests.post(f"{API_BASE}/rule-groups", json={"name": "Child Group", "description": "Nested", "parent_id": parent['id']})
    if res.status_code != 200:
        log(f"Failed to create child: {res.text}")
        return
    child = res.json()
    log(f"   Child created: {child['id']}")

    log("3. Creating Rules...")
    # Rule in parent
    requests.post(f"{API_BASE}/rule-groups/{parent['id']}/rules", json={
        "clause_number": "1.0",
        "content": "Parent Rule",
        "risk_level": "中风险"
    })
    # Rule in child
    requests.post(f"{API_BASE}/rule-groups/{child['id']}/rules", json={
        "clause_number": "1.1",
        "content": "Child Rule",
        "risk_level": "中风险"
    })

    log("4. Verifying Hierarchy (Get Groups)...")
    res = requests.get(f"{API_BASE}/rule-groups")
    groups = res.json()
    # Find parent in groups
    parent_group = next((g for g in groups if g['id'] == parent['id']), None)
    if parent_group:
        log("   Parent group found.")
        if 'children' in parent_group:
             if parent_group['children'] and len(parent_group['children']) > 0 and parent_group['children'][0]['id'] == child['id']:
                 log("   SUCCESS: Parent group contains children.")
             else:
                 log(f"   FAIL: Child ID mismatch or empty children. Children: {parent_group['children']}")
        else:
             log("   WARNING: 'children' field missing.")
    else:
        log("   FAIL: Parent group not found.")
        log(json.dumps(groups, indent=2, ensure_ascii=False))

    log("5. Verifying Cascading Delete...")
    res = requests.delete(f"{API_BASE}/rule-groups/{parent['id']}")
    if res.status_code == 200:
        log("   Parent deleted.")
    else:
        log(f"   Failed to delete parent: {res.text}")
        
    # Verify child is gone
    res = requests.get(f"{API_BASE}/rule-groups/{child['id']}")
    if res.status_code == 404:
        log("   SUCCESS: Child group is gone.")
    else:
        log(f"   FAIL: Child group still exists or error: {res.status_code}")

if __name__ == "__main__":
    try:
        test_hierarchy()
    except Exception as e:
        log(f"Test failed with exception: {e}")
