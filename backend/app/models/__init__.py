# Import all models so SQLAlchemy metadata is populated for Alembic
from app.models.department import Department  # noqa: F401
from app.models.employee import Employee, EmployeeRole, EmploymentType, EmployeeStatus  # noqa: F401
from app.models.project import Project, EmployeeProject  # noqa: F401
from app.models.skill import Skill, EmployeeSkill, Proficiency  # noqa: F401
from app.models.leave import LeaveBalance, LeaveRequest, LeaveType, LeaveStatus, HalfDayPeriod  # noqa: F401
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus  # noqa: F401
from app.models.announcement import Announcement, AnnouncementCategory  # noqa: F401
from app.models.hr_policy import HRPolicy, PolicyCategory  # noqa: F401
from app.models.payroll import PayrollRecord, PaymentStatus  # noqa: F401
from app.models.onboarding import OnboardingTask, OnboardingStatus  # noqa: F401
from app.models.job_history import JobHistory  # noqa: F401
from app.models.ai_audit_log import AIAuditLog, AIIntent, ActionStatus  # noqa: F401
from app.models.role_category_access import RoleCategoryAccess  # noqa: F401
from app.models.policy_group import PolicyGroup, GroupCategoryAccess  # noqa: F401
from app.models.conversation_memory import ConversationMemory, MemoryTier  # noqa: F401
