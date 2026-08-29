"""SQLAlchemy models for the SaaS control plane.

The scraping engine owns the scraping. This schema owns everything a business
needs on top of it: tenants, seats, credentials, metering and subscriptions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Account(Base):
    """A paying tenant. Users, API keys, jobs and usage all hang off this."""

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan_code: Mapped[str] = mapped_column(String(50), default="free", nullable=False)

    # Stripe linkage. Empty until the account starts a checkout.
    stripe_customer_id: Mapped[str] = mapped_column(String(100), default="")
    stripe_subscription_id: Mapped[str] = mapped_column(String(100), default="")
    # trialing | active | past_due | canceled | none
    subscription_status: Mapped[str] = mapped_column(String(30), default="none")
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    @property
    def is_delinquent(self) -> bool:
        return self.subscription_status in {"past_due", "unpaid"}


class User(Base):
    """A seat on an account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(20), default="owner")  # owner | member
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped[Account] = relationship(back_populates="users")


class ApiKey(Base):
    """A hashed API credential. The plaintext is shown exactly once."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), default="Default key")
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped[Account] = relationship(back_populates="api_keys")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class Job(Base):
    """One customer-visible search, mirrored from the scraping engine."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(20), default="dashboard")  # dashboard|api

    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    lang: Mapped[str] = mapped_column(String(10), default="en")
    max_depth: Mapped[int] = mapped_column(Integer, default=1)
    geo_coordinates: Mapped[str] = mapped_column(String(60), default="")
    zoom: Mapped[int] = mapped_column(Integer, default=0)
    radius: Mapped[float] = mapped_column(Float, default=0.0)
    fast_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    extract_emails: Mapped[bool] = mapped_column(Boolean, default=False)

    engine_job_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    # queued | running | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    results_json: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped[Account] = relationship(back_populates="jobs")

    @property
    def is_terminal(self) -> bool:
        return self.status in {"completed", "failed", "cancelled"}


Index("ix_jobs_account_created", Job.account_id, Job.created_at.desc())


class UsageEvent(Base):
    """Credit ledger.

    A job first writes a ``reserved`` row sized from its requested depth so a
    single large search cannot blow past the plan cap, then the row is
    reconciled to ``consumed`` with the real lead count once the engine
    finishes.
    """

    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    kind: Mapped[str] = mapped_column(String(20), default="reserved")  # reserved|consumed
    credits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("job_id", name="uq_usage_job"),)


Index("ix_usage_account_period", UsageEvent.account_id, UsageEvent.period)
