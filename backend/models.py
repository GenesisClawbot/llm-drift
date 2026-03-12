"""Database models for DriftWatch SaaS."""
import uuid
import secrets
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Boolean, DateTime, Float, Integer,
    Text, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = "sqlite:///./driftwatch.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_api_key():
    return "dw_" + secrets.token_urlsafe(32)


def generate_id():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_id)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False, default=generate_api_key)
    plan = Column(String, default="free")  # free | starter | pro
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    monitoring_active = Column(Boolean, default=False)
    slack_webhook_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    prompts = relationship("Prompt", back_populates="user", cascade="all, delete-orphan")
    results = relationship("RunResult", back_populates="user", cascade="all, delete-orphan")
    baselines = relationship("Baseline", back_populates="user", cascade="all, delete-orphan")


class Prompt(Base):
    __tablename__ = "prompts"
    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    prompt_text = Column(Text, nullable=False)
    model = Column(String, default="claude-3-haiku-20240307")
    validators = Column(Text, default="[]")   # JSON list of validator names
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="prompts")
    baselines = relationship("Baseline", back_populates="prompt", cascade="all, delete-orphan")


class Baseline(Base):
    __tablename__ = "baselines"
    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    prompt_id = Column(String, ForeignKey("prompts.id"), nullable=False)
    response = Column(Text, nullable=False)
    model = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="baselines")
    prompt = relationship("Prompt", back_populates="baselines")


class RunResult(Base):
    __tablename__ = "run_results"
    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    run_at = Column(DateTime, default=datetime.utcnow)
    avg_drift = Column(Float, default=0.0)
    max_drift = Column(Float, default=0.0)
    alert_count = Column(Integer, default=0)
    results_json = Column(Text, default="[]")  # JSON list of per-prompt results

    user = relationship("User", back_populates="results")


class AlertLog(Base):
    __tablename__ = "alert_log"
    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    run_result_id = Column(String, ForeignKey("run_results.id"), nullable=True)
    alert_type = Column(String)   # drift | regression
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered = Column(Boolean, default=False)


def create_tables():
    Base.metadata.create_all(bind=engine)
