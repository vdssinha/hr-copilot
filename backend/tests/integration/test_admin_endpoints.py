"""Integration tests for admin endpoints: users, roles, categories, policies."""
import io
import pytest

from app.models.employee import EmployeeRole
from app.models.hr_policy import PolicyCategory
from app.models.role_category_access import RoleCategoryAccess


# ── helpers ───────────────────────────────────────────────────────────────────

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def seed_rca(db_session):
    """Ensure role_category_access has full seed for integration tests."""
    existing = db_session.query(RoleCategoryAccess).count()
    if existing == 0:
        for role in EmployeeRole:
            for cat in PolicyCategory:
                db_session.add(RoleCategoryAccess(role=role.value, category=cat.value))
        db_session.commit()


# ── access control ────────────────────────────────────────────────────────────

class TestAdminAccessControl:
    def test_non_admin_forbidden_users(self, client, employee_token):
        r = client.get("/api/v1/admin/users", headers=auth(employee_token))
        assert r.status_code == 403

    def test_non_admin_forbidden_roles(self, client, manager_token):
        r = client.get("/api/v1/admin/roles", headers=auth(manager_token))
        assert r.status_code == 403

    def test_unauthenticated_rejected(self, client):
        r = client.get("/api/v1/admin/users")
        assert r.status_code == 401


# ── users ─────────────────────────────────────────────────────────────────────

class TestAdminUsers:
    def test_list_users(self, client, admin_token):
        r = client.get("/api/v1/admin/users", headers=auth(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 3  # seed_employees fixture

    def test_create_user(self, client, admin_token):
        payload = {
            "employee_code": "TST099",
            "name": "New User",
            "email": "new.user.admin.test@example.com",
            "password": "secret123",
            "role": "EMPLOYEE",
            "employment_type": "FULL_TIME",
        }
        r = client.post("/api/v1/admin/users", json=payload, headers=auth(admin_token))
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == payload["email"]
        assert data["role"] == "EMPLOYEE"

    def test_create_user_duplicate_email(self, client, admin_token):
        payload = {
            "employee_code": "TST100",
            "name": "Dup User",
            "email": "new.user.admin.test@example.com",
            "password": "secret123",
            "role": "EMPLOYEE",
            "employment_type": "FULL_TIME",
        }
        r = client.post("/api/v1/admin/users", json=payload, headers=auth(admin_token))
        assert r.status_code == 409

    def test_update_user(self, client, admin_token, db_session):
        user = db_session.query(__import__("app.models.employee", fromlist=["Employee"]).Employee).filter_by(
            email="new.user.admin.test@example.com"
        ).first()
        r = client.patch(
            f"/api/v1/admin/users/{user.id}",
            json={"role": "MANAGER"},
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["role"] == "MANAGER"

    def test_delete_user(self, client, admin_token, db_session):
        from app.models.employee import Employee
        user = db_session.query(Employee).filter_by(email="new.user.admin.test@example.com").first()
        r = client.delete(f"/api/v1/admin/users/{user.id}", headers=auth(admin_token))
        assert r.status_code == 204

    def test_delete_nonexistent_user(self, client, admin_token):
        r = client.delete("/api/v1/admin/users/999999", headers=auth(admin_token))
        assert r.status_code == 404


# ── roles ─────────────────────────────────────────────────────────────────────

class TestAdminRoles:
    def test_list_roles(self, client, admin_token):
        r = client.get("/api/v1/admin/roles", headers=auth(admin_token))
        assert r.status_code == 200
        roles = {item["name"] for item in r.json()}
        assert roles == {"EMPLOYEE", "MANAGER", "ADMIN"}

    def test_update_role_categories(self, client, admin_token):
        r = client.patch(
            "/api/v1/admin/roles/EMPLOYEE",
            json={"accessible_categories": ["LEAVE", "GENERAL"]},
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert set(data["accessible_categories"]) == {"LEAVE", "GENERAL"}

    def test_update_role_unknown_category(self, client, admin_token):
        r = client.patch(
            "/api/v1/admin/roles/EMPLOYEE",
            json={"accessible_categories": ["NONEXISTENT"]},
            headers=auth(admin_token),
        )
        assert r.status_code == 400

    def test_update_nonexistent_role(self, client, admin_token):
        r = client.patch(
            "/api/v1/admin/roles/GHOST",
            json={"accessible_categories": ["LEAVE"]},
            headers=auth(admin_token),
        )
        assert r.status_code == 404


# ── categories ────────────────────────────────────────────────────────────────

class TestAdminCategories:
    def test_list_categories(self, client, admin_token):
        r = client.get("/api/v1/admin/categories", headers=auth(admin_token))
        assert r.status_code == 200
        cats = {item["name"] for item in r.json()}
        assert "LEAVE" in cats
        assert "GENERAL" in cats

    def test_update_category_roles(self, client, admin_token):
        r = client.patch(
            "/api/v1/admin/categories/COMPENSATION",
            json={"accessible_by_roles": ["ADMIN", "MANAGER"]},
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert set(data["accessible_by_roles"]) == {"ADMIN", "MANAGER"}

    def test_update_category_unknown_role(self, client, admin_token):
        r = client.patch(
            "/api/v1/admin/categories/LEAVE",
            json={"accessible_by_roles": ["GHOST_ROLE"]},
            headers=auth(admin_token),
        )
        assert r.status_code == 400

    def test_update_nonexistent_category(self, client, admin_token):
        r = client.patch(
            "/api/v1/admin/categories/FAKECAT",
            json={"accessible_by_roles": ["ADMIN"]},
            headers=auth(admin_token),
        )
        assert r.status_code == 404


# ── policies ──────────────────────────────────────────────────────────────────

class TestAdminPolicies:
    def test_list_policies(self, client, admin_token):
        r = client.get("/api/v1/admin/policies", headers=auth(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_upload_markdown_policy(self, client, admin_token):
        content = b"# Leave Policy\n\nEmployees get 20 days of annual leave."
        r = client.post(
            "/api/v1/admin/policies/upload",
            data={"title": "Test Leave Policy", "category": "LEAVE"},
            files={"file": ("test_leave.md", io.BytesIO(content), "text/markdown")},
            headers=auth(admin_token),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["success"] is True
        assert body["data"]["status"] == "ingestion_queued"

    def test_upload_invalid_extension(self, client, admin_token):
        r = client.post(
            "/api/v1/admin/policies/upload",
            data={"title": "Bad File", "category": "GENERAL"},
            files={"file": ("file.docx", io.BytesIO(b"data"), "application/octet-stream")},
            headers=auth(admin_token),
        )
        assert r.status_code == 400

    def test_upload_invalid_category(self, client, admin_token):
        r = client.post(
            "/api/v1/admin/policies/upload",
            data={"title": "Bad Cat", "category": "NONEXISTENT"},
            files={"file": ("policy.md", io.BytesIO(b"content"), "text/markdown")},
            headers=auth(admin_token),
        )
        assert r.status_code == 400

    def test_delete_policy(self, client, admin_token, db_session):
        from app.models.hr_policy import HRPolicy
        policy = db_session.query(HRPolicy).filter_by(title="Test Leave Policy").first()
        if not policy:
            pytest.skip("Upload test did not create policy")
        r = client.delete(f"/api/v1/admin/policies/{policy.id}", headers=auth(admin_token))
        assert r.status_code == 204
        db_session.refresh(policy)
        assert policy.is_active is False

    def test_delete_nonexistent_policy(self, client, admin_token):
        r = client.delete("/api/v1/admin/policies/999999", headers=auth(admin_token))
        assert r.status_code == 404
