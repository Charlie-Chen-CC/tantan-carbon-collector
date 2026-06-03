"""API 路由聚合 - 碳管师收资系统

所有端点按职责拆到 5 个 router 文件，本文件仅做 include 聚合。
"""
from fastapi import APIRouter

from tantan.backend.api.auth import router as auth_router
from tantan.backend.api.chat_router import router as chat_router
from tantan.backend.api.extract_router import router as extract_router
from tantan.backend.api.files_router import router as files_router
from tantan.backend.api.form_router import router as form_router
from tantan.backend.api.history_router import router as history_router
from tantan.backend.api.sessions_router import router as sessions_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(sessions_router)
api_router.include_router(files_router)
api_router.include_router(extract_router)
api_router.include_router(form_router)
api_router.include_router(chat_router)
api_router.include_router(history_router)
