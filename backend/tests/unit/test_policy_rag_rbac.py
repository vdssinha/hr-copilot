"""Unit tests for role-based category filtering in policy_rag."""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _models  # noqa
from app.db.base import Base
from app.models.employee import EmployeeRole
from app.models.hr_policy import PolicyCategory
from app.models.role_category_access import RoleCategoryAccess
from app.services.ai.agents.policy_rag import _get_accessible_categories, answer_policy_question


@pytest.fixture(scope="module")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # EMPLOYEE: only LEAVE and GENERAL
    for cat in [PolicyCategory.LEAVE, PolicyCategory.GENERAL]:
        session.add(RoleCategoryAccess(role=EmployeeRole.EMPLOYEE.value, category=cat.value))
    # MANAGER: all categories
    for cat in PolicyCategory:
        session.add(RoleCategoryAccess(role=EmployeeRole.MANAGER.value, category=cat.value))
    # ADMIN: all categories
    for cat in PolicyCategory:
        session.add(RoleCategoryAccess(role=EmployeeRole.ADMIN.value, category=cat.value))
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestGetAccessibleCategories:
    def test_employee_gets_restricted_set(self, db):
        cats = _get_accessible_categories(db, EmployeeRole.EMPLOYEE)
        assert set(cats) == {"LEAVE", "GENERAL"}

    def test_manager_gets_all(self, db):
        cats = _get_accessible_categories(db, EmployeeRole.MANAGER)
        assert set(cats) == {c.value for c in PolicyCategory}

    def test_admin_gets_all(self, db):
        cats = _get_accessible_categories(db, EmployeeRole.ADMIN)
        assert set(cats) == {c.value for c in PolicyCategory}

    def test_role_with_no_access_returns_empty(self, db):
        # Remove all EMPLOYEE access rows temporarily
        db.query(RoleCategoryAccess).filter_by(role=EmployeeRole.EMPLOYEE.value).delete()
        db.commit()
        cats = _get_accessible_categories(db, EmployeeRole.EMPLOYEE)
        assert cats == []
        # Restore
        for cat in [PolicyCategory.LEAVE, PolicyCategory.GENERAL]:
            db.add(RoleCategoryAccess(role=EmployeeRole.EMPLOYEE.value, category=cat.value))
        db.commit()


class TestAnswerPolicyQuestionRBAC:
    def test_no_role_passes_no_where_filter(self, db):
        """Backward-compat: user_role=None must not filter."""
        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_embedder = MagicMock()

        with patch("app.services.ai.agents.policy_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.policy_rag._factory.get_embedder", return_value=mock_embedder), \
             patch("app.services.ai.agents.policy_rag._needs_ingestion", return_value=False):
            mock_store.similarity_search.return_value = []
            answer_policy_question(db, "test question", user_role=None)

        call_kwargs = mock_store.similarity_search.call_args
        assert call_kwargs.kwargs.get("where") is None or "where" not in str(call_kwargs)

    def test_role_passes_category_where_filter(self, db):
        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 10

        with patch("app.services.ai.agents.policy_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.policy_rag._factory.get_embedder", return_value=mock_embedder), \
             patch("app.services.ai.agents.policy_rag._needs_ingestion", return_value=False):
            mock_store.similarity_search.return_value = []
            answer_policy_question(db, "vacation days", user_role=EmployeeRole.EMPLOYEE)

        call_kwargs = mock_store.similarity_search.call_args
        where = call_kwargs.kwargs.get("where")
        assert where is not None
        assert "$in" in where.get("category", {})
        assert set(where["category"]["$in"]) == {"LEAVE", "GENERAL"}

    def test_role_with_no_access_returns_access_denied(self, db):
        """Role with zero category access gets access-denied answer without hitting vector store."""
        db.query(RoleCategoryAccess).filter_by(role=EmployeeRole.EMPLOYEE.value).delete()
        db.commit()

        mock_store = MagicMock()
        with patch("app.services.ai.agents.policy_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.policy_rag._needs_ingestion", return_value=False):
            result = answer_policy_question(db, "anything", user_role=EmployeeRole.EMPLOYEE)

        assert "do not have access" in result["answer"].lower()
        mock_store.similarity_search.assert_not_called()

        # Restore
        for cat in [PolicyCategory.LEAVE, PolicyCategory.GENERAL]:
            db.add(RoleCategoryAccess(role=EmployeeRole.EMPLOYEE.value, category=cat.value))
        db.commit()
