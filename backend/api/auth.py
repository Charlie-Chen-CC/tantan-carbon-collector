"""
认证路由 - 碳管师收资系统
用户注册、登录、Token验证
"""

import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tantan.backend.models.database import User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth")

# 安全方案
security = HTTPBearer()

# Token过期时间
TOKEN_EXPIRE_HOURS = 24 * 7  # 7天


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    enterprise_name: Optional[str] = None
    industry: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: Optional[str]
    enterprise_name: Optional[str]
    industry: Optional[str]
    created_at: str


# 简单的Token存储（生产环境应使用Redis）
_tokens = {}


def create_token(user_id: int, username: str) -> str:
    """创建访问令牌"""
    token = secrets.token_urlsafe(32)
    expire_at = datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    _tokens[token] = {
        "user_id": user_id,
        "username": username,
        "expire_at": expire_at.isoformat()
    }
    return token


def verify_token(token: str) -> Optional[dict]:
    """验证Token"""
    if token not in _tokens:
        return None

    token_data = _tokens[token]
    expire_at = datetime.fromisoformat(token_data["expire_at"])

    if datetime.now() > expire_at:
        del _tokens[token]
        return None

    return token_data


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户（依赖注入）"""
    token = credentials.credentials
    token_data = verify_token(token)

    if not token_data:
        raise HTTPException(status_code=401, detail="无效或过期的Token")

    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="用户已被禁用")

    return user


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户
    user = User(
        username=request.username,
        password_hash=User.hash_password(request.password),
        email=request.email,
        enterprise_name=request.enterprise_name,
        industry=request.industry
    )
    # 生成唯一用户ID
    user.user_id = user.generate_user_id()

    db.add(user)
    db.commit()
    db.refresh(user)

    # 创建Token
    token = create_token(user.id, user.username)

    logger.info(f"用户注册成功: {user.username} (user_id: {user.user_id})")

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        username=user.username
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == request.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not User.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="用户已被禁用")

    # 更新最后登录时间
    user.last_login_at = datetime.now()
    db.commit()

    # 创建Token
    token = create_token(user.id, user.username)

    logger.info(f"用户登录: {user.username}")

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        username=user.username
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        enterprise_name=current_user.enterprise_name,
        industry=current_user.industry,
        created_at=current_user.created_at.isoformat()
    )


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """登出"""
    token = credentials.credentials
    if token in _tokens:
        del _tokens[token]
    return {"message": "已登出"}


@router.put("/profile")
async def update_profile(
    enterprise_name: Optional[str] = None,
    industry: Optional[str] = None,
    email: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户资料"""
    if enterprise_name is not None:
        current_user.enterprise_name = enterprise_name
    if industry is not None:
        current_user.industry = industry
    if email is not None:
        current_user.email = email

    current_user.updated_at = datetime.now()
    db.commit()

    return {"message": "资料已更新"}