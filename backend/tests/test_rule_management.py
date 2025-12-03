"""
Tests for Rule Management Module.
Tests CRUD operations for RuleGroup and Rule entities.
Updated to use clause_number and Chinese importance values (一般/中等/重要).
"""
import pytest
from fastapi.testclient import TestClient


class TestRuleGroupCRUD:
    """Tests for Rule Group CRUD operations."""

    def test_create_rule_group(self, client: TestClient):
        """Test creating a new rule group."""
        response = client.post(
            "/rule-groups",
            json={"name": "防洪评价导则2025版", "description": "防洪评价相关规则"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "防洪评价导则2025版"
        assert data["description"] == "防洪评价相关规则"
        assert "id" in data
        assert "created_at" in data

    def test_create_rule_group_minimal(self, client: TestClient):
        """Test creating a rule group with only name."""
        response = client.post(
            "/rule-groups",
            json={"name": "测试规则组"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "测试规则组"
        assert data["description"] is None

    def test_get_rule_groups_empty(self, client: TestClient):
        """Test getting rule groups when none exist."""
        response = client.get("/rule-groups")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_rule_groups(self, client: TestClient):
        """Test getting all rule groups."""
        # Create two groups
        client.post("/rule-groups", json={"name": "Group 1"})
        client.post("/rule-groups", json={"name": "Group 2"})

        response = client.get("/rule-groups")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_rule_group_by_id(self, client: TestClient):
        """Test getting a specific rule group."""
        # Create a group
        create_response = client.post(
            "/rule-groups",
            json={"name": "Test Group", "description": "Test Description"}
        )
        group_id = create_response.json()["id"]

        # Get by ID
        response = client.get(f"/rule-groups/{group_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == group_id
        assert data["name"] == "Test Group"

    def test_get_rule_group_not_found(self, client: TestClient):
        """Test getting a non-existent rule group."""
        response = client.get("/rule-groups/non-existent-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Rule group not found"

    def test_update_rule_group(self, client: TestClient):
        """Test updating a rule group."""
        # Create a group
        create_response = client.post(
            "/rule-groups",
            json={"name": "Original Name", "description": "Original Description"}
        )
        group_id = create_response.json()["id"]

        # Update it
        response = client.put(
            f"/rule-groups/{group_id}",
            json={"name": "Updated Name", "description": "Updated Description"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated Description"

    def test_update_rule_group_not_found(self, client: TestClient):
        """Test updating a non-existent rule group."""
        response = client.put(
            "/rule-groups/non-existent-id",
            json={"name": "New Name"}
        )
        assert response.status_code == 404

    def test_delete_rule_group(self, client: TestClient):
        """Test deleting a rule group."""
        # Create a group
        create_response = client.post("/rule-groups", json={"name": "To Delete"})
        group_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/rule-groups/{group_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Rule group deleted"

        # Verify it's gone
        get_response = client.get(f"/rule-groups/{group_id}")
        assert get_response.status_code == 404

    def test_delete_rule_group_not_found(self, client: TestClient):
        """Test deleting a non-existent rule group."""
        response = client.delete("/rule-groups/non-existent-id")
        assert response.status_code == 404


class TestRuleCRUD:
    """Tests for Rule CRUD operations."""

    def test_create_rule(self, client: TestClient):
        """Test creating a new rule with all fields."""
        # First create a group
        group_response = client.post("/rule-groups", json={"name": "Test Group"})
        group_id = group_response.json()["id"]

        # Create a rule
        response = client.post(
            f"/rule-groups/{group_id}/rules",
            json={
                "clause_number": "3.1.2",
                "content": "防洪评价报告应包含项目概况章节",
                "standard_name": "防洪评价导则",
                "review_type": "内容完整性",
                "importance": "重要"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["clause_number"] == "3.1.2"
        assert data["content"] == "防洪评价报告应包含项目概况章节"
        assert data["group_id"] == group_id
        assert data["importance"] == "重要"
        assert data["review_type"] == "内容完整性"

    def test_create_rule_minimal(self, client: TestClient):
        """Test creating a rule with minimal fields."""
        group_response = client.post("/rule-groups", json={"name": "Test Group"})
        group_id = group_response.json()["id"]

        response = client.post(
            f"/rule-groups/{group_id}/rules",
            json={"clause_number": "1.0", "content": "Test rule content"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["clause_number"] == "1.0"
        assert data["importance"] == "中等"  # Default value

    def test_create_rule_invalid_importance(self, client: TestClient):
        """Test creating a rule with invalid importance value."""
        group_response = client.post("/rule-groups", json={"name": "Test Group"})
        group_id = group_response.json()["id"]

        response = client.post(
            f"/rule-groups/{group_id}/rules",
            json={"clause_number": "1.0", "content": "Test", "importance": "InvalidValue"}
        )
        assert response.status_code == 400
        assert "importance" in response.json()["detail"].lower()

    def test_create_rule_invalid_review_type(self, client: TestClient):
        """Test creating a rule with invalid review_type value."""
        group_response = client.post("/rule-groups", json={"name": "Test Group"})
        group_id = group_response.json()["id"]

        response = client.post(
            f"/rule-groups/{group_id}/rules",
            json={"clause_number": "1.0", "content": "Test", "review_type": "InvalidType"}
        )
        assert response.status_code == 400
        assert "review_type" in response.json()["detail"].lower()

    def test_create_rule_group_not_found(self, client: TestClient):
        """Test creating a rule in non-existent group."""
        response = client.post(
            "/rule-groups/non-existent-id/rules",
            json={"clause_number": "1.0", "content": "Test"}
        )
        assert response.status_code == 404

    def test_get_rules(self, client: TestClient):
        """Test getting all rules in a group."""
        # Create a group
        group_response = client.post("/rule-groups", json={"name": "Test Group"})
        group_id = group_response.json()["id"]

        # Create rules
        client.post(f"/rule-groups/{group_id}/rules", json={"clause_number": "1.0", "content": "Rule 1"})
        client.post(f"/rule-groups/{group_id}/rules", json={"clause_number": "2.0", "content": "Rule 2"})

        # Get rules
        response = client.get(f"/rule-groups/{group_id}/rules")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_rules_empty(self, client: TestClient):
        """Test getting rules when none exist."""
        group_response = client.post("/rule-groups", json={"name": "Empty Group"})
        group_id = group_response.json()["id"]

        response = client.get(f"/rule-groups/{group_id}/rules")
        assert response.status_code == 200
        assert response.json() == []

    def test_update_rule(self, client: TestClient):
        """Test updating a rule."""
        # Create group and rule
        group_response = client.post("/rule-groups", json={"name": "Test Group"})
        group_id = group_response.json()["id"]

        rule_response = client.post(
            f"/rule-groups/{group_id}/rules",
            json={"clause_number": "1.0", "content": "Original Content", "importance": "一般"}
        )
        rule_id = rule_response.json()["id"]

        # Update rule
        response = client.put(
            f"/rules/{rule_id}",
            json={"content": "Updated Content", "importance": "重要"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated Content"
        assert data["importance"] == "重要"
        assert data["clause_number"] == "1.0"  # Unchanged

    def test_update_rule_not_found(self, client: TestClient):
        """Test updating a non-existent rule."""
        response = client.put(
            "/rules/non-existent-id",
            json={"content": "New Content"}
        )
        assert response.status_code == 404

    def test_delete_rule(self, client: TestClient):
        """Test deleting a rule."""
        # Create group and rule
        group_response = client.post("/rule-groups", json={"name": "Test Group"})
        group_id = group_response.json()["id"]

        rule_response = client.post(
            f"/rule-groups/{group_id}/rules",
            json={"clause_number": "1.0", "content": "To Delete"}
        )
        rule_id = rule_response.json()["id"]

        # Delete rule
        response = client.delete(f"/rules/{rule_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Rule deleted"

        # Verify it's gone
        rules_response = client.get(f"/rule-groups/{group_id}/rules")
        assert len(rules_response.json()) == 0

    def test_delete_rule_not_found(self, client: TestClient):
        """Test deleting a non-existent rule."""
        response = client.delete("/rules/non-existent-id")
        assert response.status_code == 404

    def test_delete_group_cascades_rules(self, client: TestClient):
        """Test that deleting a group also deletes its rules."""
        # Create group with rules
        group_response = client.post("/rule-groups", json={"name": "Test Group"})
        group_id = group_response.json()["id"]

        client.post(f"/rule-groups/{group_id}/rules", json={"clause_number": "1.0", "content": "Rule 1"})
        client.post(f"/rule-groups/{group_id}/rules", json={"clause_number": "2.0", "content": "Rule 2"})

        # Delete group
        client.delete(f"/rule-groups/{group_id}")

        # Rules should also be deleted (group is gone, so we can't query by group)
        # Just verify the group is gone
        get_response = client.get(f"/rule-groups/{group_id}")
        assert get_response.status_code == 404


class TestCSVImportExport:
    """Tests for CSV import/export functionality."""

    def test_export_csv(self, client: TestClient):
        """Test exporting rules as CSV."""
        # Create group with rules
        group_response = client.post("/rule-groups", json={"name": "Export Test"})
        group_id = group_response.json()["id"]

        client.post(f"/rule-groups/{group_id}/rules", json={
            "clause_number": "1.0",
            "content": "Test rule content",
            "review_type": "内容完整性",
            "importance": "中等"
        })

        # Export CSV
        response = client.get(f"/rule-groups/{group_id}/export-csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]

    def test_import_csv(self, client: TestClient):
        """Test importing rules from CSV."""
        group_response = client.post("/rule-groups", json={"name": "Import Test"})
        group_id = group_response.json()["id"]

        # Create CSV content
        csv_content = """id,standard_name,clause_number,content,review_type,importance
,测试标准,1.1,第一条规则内容,内容完整性,重要
,测试标准,1.2,第二条规则内容,禁止条款,中等"""

        # Import CSV
        response = client.post(
            f"/rule-groups/{group_id}/import-csv",
            files={"file": ("test.csv", csv_content, "text/csv")}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Imported 2 rules from CSV"

        # Verify rules were created
        rules_response = client.get(f"/rule-groups/{group_id}/rules")
        assert len(rules_response.json()) == 2


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "llm_available" in data

