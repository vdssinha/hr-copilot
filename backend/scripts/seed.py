"""
Seed script — run once after `alembic upgrade head` or app startup.
Creates departments, employees, skills, projects, leave balances, tickets,
announcements, and HR policies.

Usage:
    cd backend
    python scripts/seed.py
"""
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.db.base import Base
import app.models  # noqa

from app.core.security import hash_password
from app.models.department import Department
from app.models.employee import Employee, EmployeeRole, EmploymentType, EmployeeStatus
from app.models.project import Project, EmployeeProject, ProjectStatus
from app.models.skill import Skill, EmployeeSkill, Proficiency
from app.models.leave import LeaveBalance, LeaveRequest, LeaveType, LeaveStatus
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus
from app.models.announcement import Announcement, AnnouncementCategory
from app.models.hr_policy import HRPolicy, PolicyCategory
from app.models.payroll import PayrollRecord, PaymentStatus
from app.models.job_history import JobHistory
from app.models.onboarding import OnboardingTask, OnboardingStatus


POLICY_DIR = Path(__file__).parent.parent / "data" / "policies"

# Maps subdirectory name → PolicyCategory
_SUBDIR_CATEGORY: dict[str, "PolicyCategory"] = {}  # populated after import

_SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}


def _build_subdir_map() -> dict[str, "PolicyCategory"]:
    from app.models.hr_policy import PolicyCategory
    return {
        "leave": PolicyCategory.LEAVE,
        "attendance": PolicyCategory.ATTENDANCE,
        "code_of_conduct": PolicyCategory.CODE_OF_CONDUCT,
        "benefits": PolicyCategory.BENEFITS,
        "compensation": PolicyCategory.COMPENSATION,
        "it": PolicyCategory.IT,
        "general": PolicyCategory.GENERAL,
    }


def load_policy_content(filename: str) -> str:
    path = POLICY_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"# {filename}\n\nPolicy content not found."


def _extract_text_from_path(path: Path) -> str:
    """Extract plain text from .md / .txt / .pdf / .docx."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.services.ai.document_loader import extract_text
    return extract_text(path)


def seed(db: Session) -> None:
    # ── Departments (no head yet — set after employees created) ──────────────
    eng = Department(name="Engineering", description="Product engineering and platform teams")
    hr_dept = Department(name="People Operations", description="HR, recruitment, and employee experience")
    sales = Department(name="Sales & Customer Success", description="Revenue and client relationships")
    db.add_all([eng, hr_dept, sales])
    db.flush()

    # ── Employees ─────────────────────────────────────────────────────────────
    admin = Employee(
        employee_code="NW-001",
        name="Priya Sharma",
        email="priya.sharma@novaworks.in",
        hashed_password=hash_password("Admin@1234"),
        role=EmployeeRole.ADMIN,
        department_id=hr_dept.id,
        job_title="HR Director",
        employment_type=EmploymentType.FULL_TIME,
        status=EmployeeStatus.ACTIVE,
        joining_date=date(2021, 3, 1),
        date_of_birth=date(1985, 6, 15),
        current_salary_usd=12000.0,
        bank_account_number="9876543210",
        bank_account_name="Priya Sharma",
        bank_branch="HDFC Koramangala",
        bank_ifsc="HDFC0001234",
        pan_number="ABCPS1234Z",
    )

    mgr_eng = Employee(
        employee_code="NW-002",
        name="Arjun Mehta",
        email="arjun.mehta@novaworks.in",
        hashed_password=hash_password("Manager@1234"),
        role=EmployeeRole.MANAGER,
        department_id=eng.id,
        job_title="Engineering Manager",
        employment_type=EmploymentType.FULL_TIME,
        status=EmployeeStatus.ACTIVE,
        joining_date=date(2022, 1, 10),
        date_of_birth=date(1988, 9, 22),
        current_salary_usd=9000.0,
    )

    mgr_sales = Employee(
        employee_code="NW-003",
        name="Sneha Iyer",
        email="sneha.iyer@novaworks.in",
        hashed_password=hash_password("Manager@1234"),
        role=EmployeeRole.MANAGER,
        department_id=sales.id,
        job_title="Sales Manager",
        employment_type=EmploymentType.FULL_TIME,
        status=EmployeeStatus.ACTIVE,
        joining_date=date(2022, 6, 1),
        date_of_birth=date(1990, 3, 5),
        current_salary_usd=8500.0,
    )

    emp1 = Employee(
        employee_code="NW-004",
        name="Rahul Verma",
        email="rahul.verma@novaworks.in",
        hashed_password=hash_password("Employee@1234"),
        role=EmployeeRole.EMPLOYEE,
        department_id=eng.id,
        job_title="AI Engineer",
        employment_type=EmploymentType.FULL_TIME,
        status=EmployeeStatus.ACTIVE,
        joining_date=date(2023, 4, 1),
        date_of_birth=date(1995, 11, 20),
        current_salary_usd=6000.0,
    )

    emp2 = Employee(
        employee_code="NW-005",
        name="Kavya Nair",
        email="kavya.nair@novaworks.in",
        hashed_password=hash_password("Employee@1234"),
        role=EmployeeRole.EMPLOYEE,
        department_id=eng.id,
        job_title="Backend Engineer",
        employment_type=EmploymentType.FULL_TIME,
        status=EmployeeStatus.ACTIVE,
        joining_date=date(2023, 7, 15),
        date_of_birth=date(1997, 2, 8),
        current_salary_usd=5500.0,
    )

    emp3 = Employee(
        employee_code="NW-006",
        name="Dev Patel",
        email="dev.patel@novaworks.in",
        hashed_password=hash_password("Employee@1234"),
        role=EmployeeRole.EMPLOYEE,
        department_id=eng.id,
        job_title="Frontend Engineer",
        employment_type=EmploymentType.FULL_TIME,
        status=EmployeeStatus.ACTIVE,
        joining_date=date(2024, 1, 8),
        date_of_birth=date(1998, 7, 14),
        current_salary_usd=5000.0,
    )

    emp4 = Employee(
        employee_code="NW-007",
        name="Meera Krishnan",
        email="meera.krishnan@novaworks.in",
        hashed_password=hash_password("Employee@1234"),
        role=EmployeeRole.EMPLOYEE,
        department_id=sales.id,
        job_title="Customer Success Manager",
        employment_type=EmploymentType.FULL_TIME,
        status=EmployeeStatus.ACTIVE,
        joining_date=date(2023, 9, 1),
        date_of_birth=date(1994, 5, 30),
        current_salary_usd=5200.0,
    )

    emp5 = Employee(
        employee_code="NW-008",
        name="Aditya Singh",
        email="aditya.singh@novaworks.in",
        hashed_password=hash_password("Employee@1234"),
        role=EmployeeRole.EMPLOYEE,
        department_id=hr_dept.id,
        job_title="HR Executive",
        employment_type=EmploymentType.FULL_TIME,
        status=EmployeeStatus.ACTIVE,
        joining_date=date(2024, 3, 15),
        date_of_birth=date(1996, 12, 1),
        current_salary_usd=4500.0,
    )

    db.add_all([admin, mgr_eng, mgr_sales, emp1, emp2, emp3, emp4, emp5])
    db.flush()

    # Set manager_id for employees
    emp1.manager_id = mgr_eng.id
    emp2.manager_id = mgr_eng.id
    emp3.manager_id = mgr_eng.id
    emp4.manager_id = mgr_sales.id
    emp5.manager_id = admin.id

    # Set department heads
    eng.head_id = mgr_eng.id
    hr_dept.head_id = admin.id
    sales.head_id = mgr_sales.id
    db.flush()

    # ── Skills ────────────────────────────────────────────────────────────────
    skills_data = [
        ("Python", "Programming"), ("FastAPI", "Backend"), ("React", "Frontend"),
        ("TypeScript", "Frontend"), ("LangChain", "AI/ML"), ("LangGraph", "AI/ML"),
        ("ChromaDB", "AI/ML"), ("SQL", "Database"), ("SQLAlchemy", "Backend"),
        ("HR Management", "Operations"), ("Sales Strategy", "Business"),
        ("Customer Success", "Business"), ("Docker", "DevOps"), ("AWS", "Cloud"),
        ("Data Analysis", "Analytics"),
    ]
    skills = {}
    for name, category in skills_data:
        s = Skill(name=name, category=category)
        db.add(s)
        skills[name] = s
    db.flush()

    # Assign skills to employees
    skill_assignments = [
        (emp1, [("Python", Proficiency.EXPERT), ("FastAPI", Proficiency.EXPERT),
                ("LangChain", Proficiency.INTERMEDIATE), ("LangGraph", Proficiency.BEGINNER),
                ("SQL", Proficiency.INTERMEDIATE)]),
        (emp2, [("Python", Proficiency.INTERMEDIATE), ("FastAPI", Proficiency.INTERMEDIATE),
                ("SQLAlchemy", Proficiency.EXPERT), ("Docker", Proficiency.INTERMEDIATE)]),
        (emp3, [("React", Proficiency.EXPERT), ("TypeScript", Proficiency.EXPERT),
                ("Python", Proficiency.BEGINNER)]),
        (emp4, [("Sales Strategy", Proficiency.EXPERT), ("Customer Success", Proficiency.EXPERT),
                ("Data Analysis", Proficiency.INTERMEDIATE)]),
        (emp5, [("HR Management", Proficiency.INTERMEDIATE), ("Data Analysis", Proficiency.BEGINNER)]),
        (mgr_eng, [("Python", Proficiency.EXPERT), ("AWS", Proficiency.INTERMEDIATE),
                   ("Docker", Proficiency.EXPERT)]),
        (mgr_sales, [("Sales Strategy", Proficiency.EXPERT), ("Customer Success", Proficiency.INTERMEDIATE)]),
    ]
    for emp, skill_list in skill_assignments:
        for skill_name, proficiency in skill_list:
            db.add(EmployeeSkill(employee_id=emp.id, skill_id=skills[skill_name].id, proficiency=proficiency))

    # ── Projects ──────────────────────────────────────────────────────────────
    proj_copilot = Project(
        name="HR Policy Copilot",
        description="AI-powered HR operations copilot built on CB Nest HRMS",
        status=ProjectStatus.ONGOING,
        start_date=date(2026, 1, 15),
    )
    proj_crm = Project(
        name="Sales CRM Integration",
        description="Integrate third-party CRM with the NovaWorks sales pipeline",
        status=ProjectStatus.ONGOING,
        start_date=date(2026, 2, 1),
    )
    proj_infra = Project(
        name="Infrastructure Migration",
        description="Migrate on-premise services to AWS",
        status=ProjectStatus.PLANNING,
        start_date=date(2026, 6, 1),
    )
    db.add_all([proj_copilot, proj_crm, proj_infra])
    db.flush()

    project_assignments = [
        (emp1, proj_copilot, "AI Engineer"),
        (emp2, proj_copilot, "Backend Engineer"),
        (emp3, proj_copilot, "Frontend Engineer"),
        (mgr_eng, proj_copilot, "Tech Lead"),
        (emp4, proj_crm, "Customer Success Lead"),
        (mgr_sales, proj_crm, "Project Sponsor"),
        (emp2, proj_infra, "DevOps Support"),
        (mgr_eng, proj_infra, "Architect"),
    ]
    for emp, proj, role in project_assignments:
        db.add(EmployeeProject(employee_id=emp.id, project_id=proj.id, role=role))

    # ── Leave Balances (2026) ─────────────────────────────────────────────────
    all_employees = [admin, mgr_eng, mgr_sales, emp1, emp2, emp3, emp4, emp5]
    for emp in all_employees:
        db.add(LeaveBalance(
            employee_id=emp.id, year=2026,
            casual_leave_total=12.0, casual_leave_used=0.0,
            sick_leave_total=12.0, sick_leave_used=0.0,
            annual_leave_total=15.0, annual_leave_used=0.0,
        ))

    # ── Leave Requests ────────────────────────────────────────────────────────
    lr1 = LeaveRequest(
        employee_id=emp1.id,
        leave_type=LeaveType.CASUAL,
        start_date=date(2026, 5, 12),
        end_date=date(2026, 5, 12),
        reason="Personal work",
        status=LeaveStatus.PENDING,
    )
    lr2 = LeaveRequest(
        employee_id=emp2.id,
        leave_type=LeaveType.SICK,
        start_date=date(2026, 4, 20),
        end_date=date(2026, 4, 22),
        reason="Fever",
        status=LeaveStatus.APPROVED,
        approved_by_id=mgr_eng.id,
        approved_at=datetime(2026, 4, 20, 9, 30),
    )
    db.add_all([lr1, lr2])

    # ── Tickets ───────────────────────────────────────────────────────────────
    t1 = Ticket(
        title="VPN not connecting from home",
        description="Getting authentication error when connecting to company VPN from home network.",
        category=TicketCategory.IT,
        priority=TicketPriority.HIGH,
        status=TicketStatus.OPEN,
        created_by_id=emp1.id,
    )
    t2 = Ticket(
        title="Laptop keyboard not working properly",
        description="Several keys are sticking on company-issued MacBook Pro.",
        category=TicketCategory.IT,
        priority=TicketPriority.MEDIUM,
        status=TicketStatus.IN_PROGRESS,
        created_by_id=emp3.id,
        assigned_to_id=mgr_eng.id,
    )
    t3 = Ticket(
        title="Leave balance not updating correctly",
        description="My leave balance shows incorrect days after recent approved leave.",
        category=TicketCategory.HR,
        priority=TicketPriority.MEDIUM,
        status=TicketStatus.OPEN,
        created_by_id=emp2.id,
    )
    db.add_all([t1, t2, t3])

    # ── Announcements ─────────────────────────────────────────────────────────
    a1 = Announcement(
        title="Q2 2026 All-Hands Meeting — May 15",
        content="Join us for the Q2 All-Hands on May 15, 2026 at 4:00 PM IST via Zoom. The leadership team will share company updates, Q1 results, and roadmap for the rest of the year. Please block your calendars. Recording will be shared post-meeting.",
        category=AnnouncementCategory.GENERAL,
        is_pinned=True,
        created_by_id=admin.id,
    )
    a2 = Announcement(
        title="New WFH Policy Effective June 1",
        content="We are updating our Work From Home policy effective June 1, 2026. Employees will now be eligible for up to 3 WFH days per week (up from 2). Please review the updated policy in the HR portal. Reach out to PeopleOps for any questions.",
        category=AnnouncementCategory.HR,
        is_pinned=False,
        created_by_id=admin.id,
    )
    db.add_all([a1, a2])

    # ── HR Policies ───────────────────────────────────────────────────────────
    policy_files = [
        ("Leave Policy", PolicyCategory.LEAVE, "seed_policy_01_leave.md"),
        ("Work From Home Policy", PolicyCategory.ATTENDANCE, "seed_policy_02_wfh.md"),
        ("Attendance Policy", PolicyCategory.ATTENDANCE, "seed_policy_03_attendance.md"),
        ("Code of Conduct Policy", PolicyCategory.CODE_OF_CONDUCT, "seed_policy_04_code_of_conduct.md"),
        ("Employee Benefits Policy", PolicyCategory.BENEFITS, "seed_policy_05_benefits.md"),
    ]
    existing_titles: set[str] = set()
    for title, category, filename in policy_files:
        content = load_policy_content(filename)
        db.add(HRPolicy(
            title=title,
            content=content,
            category=category,
            filename=filename,
            is_active=True,
            created_by_id=admin.id,
        ))
        existing_titles.add(title)

    # ── Auto-scan data/policies/{category}/ subdirectories ────────────────────
    subdir_map = _build_subdir_map()
    for subdir, cat in subdir_map.items():
        subdir_path = POLICY_DIR / subdir
        if not subdir_path.is_dir():
            continue
        for file_path in sorted(subdir_path.iterdir()):
            if file_path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                continue
            title = file_path.stem.replace("_", " ").replace("-", " ").title()
            if title in existing_titles:
                continue
            try:
                content = _extract_text_from_path(file_path)
            except Exception as e:
                print(f"  [skip] {file_path.name}: {e}")
                continue
            db.add(HRPolicy(
                title=title,
                content=content,
                category=cat,
                filename=file_path.name,
                is_active=True,
                created_by_id=admin.id,
            ))
            existing_titles.add(title)
            print(f"  [policy] {file_path.name} → {cat.value}")

    # ── Job History ───────────────────────────────────────────────────────────
    db.add(JobHistory(
        employee_id=emp1.id,
        job_title="Junior AI Engineer",
        department_id=eng.id,
        start_date=date(2023, 4, 1),
        end_date=date(2024, 9, 30),
        reason_for_change="Promoted to AI Engineer",
    ))

    # ── Payroll Records (April 2026) ─────────────────────────────────────────
    payroll_data = [
        (admin, 12000.0, 1200.0, 600.0),
        (mgr_eng, 9000.0, 900.0, 450.0),
        (mgr_sales, 8500.0, 850.0, 425.0),
        (emp1, 6000.0, 600.0, 300.0),
        (emp2, 5500.0, 550.0, 275.0),
        (emp3, 5000.0, 500.0, 250.0),
        (emp4, 5200.0, 520.0, 260.0),
        (emp5, 4500.0, 450.0, 225.0),
    ]
    for emp, basic, allowances, deductions in payroll_data:
        db.add(PayrollRecord(
            employee_id=emp.id,
            month=4,
            year=2026,
            basic_salary_usd=basic,
            allowances_usd=allowances,
            deductions_usd=deductions,
            net_salary_usd=basic + allowances - deductions,
            payment_date=date(2026, 4, 30),
            payment_status=PaymentStatus.PAID,
        ))

    # ── Onboarding tasks for newest employee ─────────────────────────────────
    tasks = [
        ("Complete IT setup", "Set up laptop, email, and required software accounts"),
        ("Review company policies", "Read and acknowledge all HR policies in CB Nest"),
        ("Meet with manager", "1:1 introductory call with direct manager"),
        ("Join team channels", "Join relevant Slack channels and project groups"),
    ]
    for task_name, description in tasks:
        db.add(OnboardingTask(
            employee_id=emp5.id,
            task_name=task_name,
            description=description,
            status=OnboardingStatus.COMPLETED,
            completed_at=datetime(2026, 3, 20),
        ))

    db.commit()
    print("Seed completed successfully.")
    print("\nTest credentials:")
    print("  Admin:    priya.sharma@novaworks.in  / Admin@1234")
    print("  Manager:  arjun.mehta@novaworks.in   / Manager@1234")
    print("  Employee: rahul.verma@novaworks.in   / Employee@1234")


HR_DATA_CSV = Path(__file__).parent.parent / "data" / "hr" / "hr_data.csv"


def seed_hr_data() -> None:
    from app.services.ai.hr_data_rag import ingest_hr_data
    if not HR_DATA_CSV.exists():
        print("  [skip] hr_data.csv not found")
        return
    count = ingest_hr_data(HR_DATA_CSV)
    print(f"  [hr_data] ingested {count} chunks from {HR_DATA_CSV.name}")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(Employee).first()
        if existing:
            print("Database already seeded. Run with --force to re-seed.")
            import sys
            if "--force" not in sys.argv:
                sys.exit(0)
            # Drop and recreate
            db.close()
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            db = SessionLocal()

        seed(db)

        print("\nIngesting HR employee data into vector store…")
        seed_hr_data()

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()
