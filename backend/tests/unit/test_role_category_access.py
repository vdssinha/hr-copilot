"""Unit tests for RoleCategoryAccess model and seed data invariants."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _models  # noqa — registers all models
from app.db.base import Base
from app.models.employee import EmployeeRole
from app.models.hr_policy import PolicyCategory
from app.models.role_category_access import RoleCategoryAccess


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

    # Seed all roles x all categories (mirrors migration 002)
    for role in EmployeeRole:
        for cat in PolicyCategory:
            session.add(RoleCategoryAccess(role=role.value, category=cat.value))
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_all_roles_seeded(db):
    rows = db.query(RoleCategoryAccess).all()
    assert len(rows) == len(EmployeeRole) * len(PolicyCategory)


def test_each_role_has_all_categories(db):
    for role in EmployeeRole:
        cats = {
            r.category
            for r in db.query(RoleCategoryAccess)
            .filter(RoleCategoryAccess.role == role.value)
            .all()
        }
        assert cats == {c.value for c in PolicyCategory}


def test_primary_key_uniqueness(db):
    """Inserting a duplicate (role, category) pair must raise."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db.add(RoleCategoryAccess(role=EmployeeRole.EMPLOYEE.value, category=PolicyCategory.LEAVE.value))
        db.flush()
    db.rollback()


def test_get_categories_for_role(db):
    cats = [
        r.category
        for r in db.query(RoleCategoryAccess)
        .filter(RoleCategoryAccess.role == EmployeeRole.ADMIN.value)
        .all()
    ]
    assert PolicyCategory.GENERAL.value in cats
    assert PolicyCategory.COMPENSATION.value in cats


def test_delete_access_removes_row(db):
    db.query(RoleCategoryAccess).filter_by(
        role=EmployeeRole.EMPLOYEE.value, category=PolicyCategory.COMPENSATION.value
    ).delete()
    db.commit()

    row = db.query(RoleCategoryAccess).filter_by(
        role=EmployeeRole.EMPLOYEE.value, category=PolicyCategory.COMPENSATION.value
    ).first()
    assert row is None

    # Restore for other tests
    db.add(RoleCategoryAccess(role=EmployeeRole.EMPLOYEE.value, category=PolicyCategory.COMPENSATION.value))
    db.commit()
