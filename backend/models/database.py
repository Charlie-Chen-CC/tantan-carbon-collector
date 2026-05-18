"""
数据库模型 - 碳管师收资系统
使用SQLAlchemy ORM连接PostgreSQL
"""

import hashlib
import secrets
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

from tantan.backend.config import get_config

DATABASE_URL = get_config().DATABASE_URL
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), unique=True, index=True, nullable=False)  # 唯一用户ID
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    email = Column(String(255), nullable=True)
    enterprise_name = Column(String(255), nullable=True)  # 企业名称
    industry = Column(String(100), nullable=True)  # 所属行业
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    # 关系
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
        return f"{salt}${pwd_hash}"

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            salt, pwd_hash = password_hash.split('$')
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
            return new_hash == pwd_hash
        except:
            return False

    def generate_user_id(self) -> str:
        """生成唯一用户ID"""
        return f"U-{secrets.token_hex(8).upper()}"


class Session(Base):
    """会话表"""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 关联用户
    enterprise_name = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=True)
    contact_person = Column(String(100), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    production_address = Column(String(500), nullable=True)
    accounting_year = Column(String(20), nullable=True)
    current_section = Column(Integer, default=1)
    status = Column(String(20), default="active")  # active, completed, archived
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    user = relationship("User", back_populates="sessions")
    section_data = relationship("SectionData", back_populates="session", cascade="all, delete-orphan")
    operation_history = relationship("OperationHistory", back_populates="session", cascade="all, delete-orphan")


class SectionData(Base):
    """部分数据表"""
    __tablename__ = "section_data"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    section_number = Column(Integer, nullable=False)  # 1-9
    data = Column(JSON, nullable=True)
    status = Column(String(20), default="not_started")  # not_started, in_progress, completed
    file_path = Column(String(500), nullable=True)  # 上传的文件路径
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    session = relationship("Session", back_populates="section_data")


class OperationHistory(Base):
    """操作历史表"""
    __tablename__ = "operation_history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # file_upload, form_fill, chat, modify
    section_number = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    # 关系
    session = relationship("Session", back_populates="operation_history")


class UploadedFile(Base):
    """上传文件表"""
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    file_type = Column(String(50), nullable=True)
    section_number = Column(Integer, nullable=True)  # 上传时针对的部分
    status = Column(String(20), default="pending")  # pending, processed, failed
    created_at = Column(DateTime, default=datetime.now)
    processed_at = Column(DateTime, nullable=True)


class ConversationHistory(Base):
    """对话历史表"""
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    message = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话（generator版本，用于FastAPI依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseContext:
    """数据库会话上下文管理器"""

    def __enter__(self):
        self.db = SessionLocal()
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
        return False


def get_db_context():
    """获取数据库会话上下文管理器（用于StateManager等）"""
    return DatabaseContext()
