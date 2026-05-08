from fastapi import APIRouter
from app.api.v1.endpoints import admin, auth, chat

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
