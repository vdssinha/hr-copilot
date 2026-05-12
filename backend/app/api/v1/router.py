from fastapi import APIRouter
from app.api.v1.endpoints import admin, auth, chat, leaves, tickets, announcements, projects

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(leaves.router, prefix="/leaves", tags=["leaves"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(announcements.router, prefix="/announcements", tags=["announcements"])
api_router.include_router(projects.router, prefix="", tags=["projects"])
