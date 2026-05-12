"""
Announcement business logic — single source of truth for all announcement operations.
Called by both api_tools.py (AI agent path) and REST endpoints.
"""
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmployeeRole
from app.models.announcement import Announcement, AnnouncementCategory


def create_announcement(
    db: Session,
    actor: Employee,
    title: str,
    content: str,
    category: str = "GENERAL",
    is_pinned: bool = False,
) -> dict:
    if actor.role == EmployeeRole.EMPLOYEE:
        return {"success": False, "error": "You do not have permission to create announcements."}

    try:
        cat = AnnouncementCategory[category.upper()]
    except KeyError:
        cat = AnnouncementCategory.GENERAL

    ann = Announcement(
        title=title,
        content=content,
        category=cat,
        is_pinned=is_pinned,
        created_by_id=actor.id,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return {"success": True, "data": {"id": ann.id, "title": title}}
