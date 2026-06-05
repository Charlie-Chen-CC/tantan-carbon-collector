"""
认证路由 - 碳管师收资系统
用户注册、登录、Token验证
"""

import secrets
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Optional

import redis
from fastapi import APIRouter, Depends, Response, Cookie, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tantan.backend.models.database import User, get_db
from tantan.backend.config import get_config
from tantan.backend.utils import limit_auth
from tantan.backend.utils.exceptions import AppException, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth")

# 安全方案
security = HTTPBearer()

# Token过期时间
TOKEN_EXPIRE_HOURS = 24 * 7  # 7天
TOKEN_PREFIX = "auth:token:"
AUTH_COOKIE_NAME = "auth_token"


def is_production() -> bool:
    """判断是否为生产环境"""
    return get_config().ENVIRONMENT == "production"


def is_redis_available() -> bool:
    """检查Redis是否可用"""
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        return True
    except Exception:
        return False


def get_redis_client():
    """获取Redis客户端（用于Token存储）"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


# 开发模式下降级方案：内存存储
_token_store: dict = {}


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


def create_token(user_id: int, username: str) -> str:
    """创建访问令牌（优先Redis，失败时降级到内存）"""
    token = secrets.token_urlsafe(32)
    token_data = {
        "user_id": user_id,
        "username": username,
        "created_at": datetime.now().isoformat()
    }

    # 尝试Redis存储
    if is_redis_available():
        try:
            redis_client = get_redis_client()
            redis_client.setex(
                f"{TOKEN_PREFIX}{token}",
                TOKEN_EXPIRE_HOURS * 3600,
                json.dumps(token_data)
            )
            logger.info(f"Token已存储到Redis: user_id={user_id}")
            return token
        except redis.RedisError as e:
            logger.warning(f"Redis存储Token失败: {e}，降级到内存存储")

    # 降级到内存存储
    _token_store[token] = token_data
    logger.warning(f"Token使用内存存储（仅限开发环境）: user_id={user_id}")
    return token


def verify_token(token: str) -> Optional[dict]:
    """验证Token（优先Redis，失败时降级到内存）"""
    logger.info(f"verify_token called: token={'有值: ' + token[:20] + '...' if token else 'None/空'}")

    if not token:
        logger.warning("verify_token: token为空字符串")
        return None

    # 尝试从Redis获取
    if is_redis_available():
        try:
            redis_client = get_redis_client()
            token_json = redis_client.get(f"{TOKEN_PREFIX}{token}")
            if token_json:
                logger.info(f"verify_token: 从Redis找到token, value={token_json}")
                return json.loads(token_json)
            else:
                logger.warning(f"verify_token: Redis中未找到token (key: {TOKEN_PREFIX}{token[:20]}...)")
        except redis.RedisError as e:
            logger.error(f"Redis验证Token失败: {e}")

    # 降级到内存存储
    result = _token_store.get(token)
    logger.info(f"verify_token: 内存存储 {'找到' if result else '未找到'} token, 内存中共有 {len(_token_store)} 个token")
    return result


def get_current_user(
    response: Response,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户（依赖注入 - httpOnly Cookie 方式）

    旧 Bearer Token 方式已废弃：前端不再写 Authorization 头，统一靠浏览器自动携带 httpOnly Cookie。
    """
    if not auth_token:
        raise AppException(
            ErrorCode.AUTH_REQUIRED,
            "未登录或Token已过期",
            status_code=401,
        )

    token_data = verify_token(auth_token)
    if not token_data:
        # Token已过期或无效，清除cookie
        response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
        raise AppException(
            ErrorCode.AUTH_TOKEN_EXPIRED,
            "Token已过期，请重新登录",
            status_code=401,
        )

    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    if not user:
        response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
        raise AppException(
            ErrorCode.AUTH_INVALID_CREDENTIALS,
            "用户不存在",
            status_code=401,
        )

    if not user.is_active:
        raise AppException(
            ErrorCode.AUTH_USER_DISABLED,
            "用户已被禁用",
            status_code=401,
        )

    return user


async def get_current_user_from_cookie(
    response: Response,
    auth_token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
    db: Session = Depends(get_db)
) -> User:
    """[已废弃] 请改用 get_current_user。保留仅为兼容老调用方。"""
    return get_current_user(response, auth_token, db)


@router.post("/register", response_model=TokenResponse)
@limit_auth
async def register(body: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise AppException(
            ErrorCode.INVALID_REQUEST,
            "用户名已存在",
            status_code=400,
        )

    # 创建用户
    user = User(
        username=body.username,
        password_hash=User.hash_password(body.password),
        email=body.email,
        enterprise_name=body.enterprise_name,
        industry=body.industry
    )
    # 生成唯一用户ID
    user.user_id = user.generate_user_id()

    db.add(user)
    db.commit()
    db.refresh(user)

    # 创建Token
    token = create_token(user.id, user.username)

    # 设置 httpOnly cookie（生产环境启用 secure；SameSite 默认 strict，防御 CSRF）
    config = get_config()
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=TOKEN_EXPIRE_HOURS * 3600,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        path="/"
    )

    logger.info(f"用户注册成功: {user.username} (user_id: {user.user_id})")

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        username=user.username
    )


@router.post("/login", response_model=TokenResponse)
@limit_auth
async def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == body.username).first()

    if not user:
        raise AppException(
            ErrorCode.AUTH_INVALID_CREDENTIALS,
            "用户名或密码错误",
            status_code=401,
        )

    if not User.verify_password(body.password, user.password_hash):
        raise AppException(
            ErrorCode.AUTH_INVALID_CREDENTIALS,
            "用户名或密码错误",
            status_code=401,
        )

    if not user.is_active:
        raise AppException(
            ErrorCode.AUTH_USER_DISABLED,
            "用户已被禁用",
            status_code=401,
        )

    # 更新最后登录时间
    user.last_login_at = datetime.now()
    db.commit()

    # 创建Token
    token = create_token(user.id, user.username)

    # 设置 httpOnly cookie（生产环境启用 secure；SameSite 默认 strict，防御 CSRF）
    config = get_config()
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=TOKEN_EXPIRE_HOURS * 3600,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        path="/"
    )

    logger.info(f"用户登录: {user.username}")

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        username=user.username
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息（Bearer Token方式）"""
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        enterprise_name=current_user.enterprise_name,
        industry=current_user.industry,
        created_at=current_user.created_at.isoformat()
    )


@router.get("/me/cookie", response_model=UserResponse)
async def get_me_cookie(
    response: Response,
    current_user: User = Depends(get_current_user_from_cookie)
):
    """获取当前用户信息（Cookie方式）"""
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        enterprise_name=current_user.enterprise_name,
        industry=current_user.industry,
        created_at=current_user.created_at.isoformat()
    )


@router.post("/logout")
async def logout(response: Response, auth_token: Optional[str] = Cookie(None)):
    """登出"""
    if auth_token:
        try:
            redis_client = get_redis_client()
            redis_client.delete(f"{TOKEN_PREFIX}{auth_token}")
        except redis.RedisError as e:
            logger.warning(f"Redis删除Token失败: {e}，但用户已登出")

    # 清除cookie
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
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
