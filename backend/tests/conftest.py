"""
Shared fixtures: in-memory SQLite DB, TestClient, per-role employees + JWT tokens.
Uses StaticPool so all connections share the same in-memory database.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.employee import Employee, EmployeeRole, EmploymentType, EmployeeStatus
import app.models as _app_models  # noqa — registers all models with Base.metadata


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture(scope="session")
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="session")
def seed_employees(db_session):
    employees = {
        "employee": Employee(
            employee_code="EMP001",
            name="Test Employee",
            email="test.employee@test.com",
            hashed_password=hash_password("testpass"),
            role=EmployeeRole.EMPLOYEE,
            employment_type=EmploymentType.FULL_TIME,
            status=EmployeeStatus.ACTIVE,
        ),
        "manager": Employee(
            employee_code="MGR001",
            name="Test Manager",
            email="test.manager@test.com",
            hashed_password=hash_password("testpass"),
            role=EmployeeRole.MANAGER,
            employment_type=EmploymentType.FULL_TIME,
            status=EmployeeStatus.ACTIVE,
        ),
        "admin": Employee(
            employee_code="ADM001",
            name="Test Admin",
            email="test.admin@test.com",
            hashed_password=hash_password("testpass"),
            role=EmployeeRole.ADMIN,
            employment_type=EmploymentType.FULL_TIME,
            status=EmployeeStatus.ACTIVE,
        ),
    }
    for emp in employees.values():
        db_session.add(emp)
    db_session.commit()
    for emp in employees.values():
        db_session.refresh(emp)
    return employees


def _make_token(employee: Employee) -> str:
    return create_access_token({"sub": str(employee.id), "role": employee.role.value})


@pytest.fixture(scope="session")
def client(db_session, seed_employees):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def employee_token(seed_employees):
    return _make_token(seed_employees["employee"])


@pytest.fixture(scope="session")
def manager_token(seed_employees):
    return _make_token(seed_employees["manager"])


@pytest.fixture(scope="session")
def admin_token(seed_employees):
    return _make_token(seed_employees["admin"])
