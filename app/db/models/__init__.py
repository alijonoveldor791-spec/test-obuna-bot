"""Relational domain models."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class User(Base):
    """Telegram participant."""

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(256))
    lang: Mapped[str] = mapped_column(String(8), default="uz")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_banned: Mapped[bool] = mapped_column(default=False)
    is_blocked: Mapped[bool] = mapped_column(default=False)
    referrer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_subscribed: Mapped[bool] = mapped_column(default=False)
    left_channel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Channel(Base):
    """Subscription and publishing channel."""

    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(256))
    username: Mapped[str | None] = mapped_column(String(64))
    invite_link: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(default=True)
    is_main: Mapped[bool] = mapped_column(default=False)


class Test(Base):
    """PDF test with publication lifecycle."""

    __tablename__ = "tests"
    __test__ = False
    __table_args__ = (
        CheckConstraint("max_attempts = 1", name="ck_tests_single_attempt"),
        CheckConstraint("status IN ('draft','active','closed')", name="ck_tests_lifecycle"),
        CheckConstraint(
            "questions_count > 0 AND max_attempts > 0 AND referral_count >= 0 AND prizes_count >= 0"
        ),
        CheckConstraint(
            "length(code) = 4 AND code >= '1000' AND code <= '9999' AND "
            "replace(replace(replace(replace(replace(replace(replace(replace("
            "replace(replace(code,'0',''),'1',''),'2',''),'3',''),'4',''),"
            "'5',''),'6',''),'7',''),'8',''),'9','') = ''",
            name="ck_tests_code_digits",
        ),
        Index(
            "uq_tests_open_code",
            "code",
            unique=True,
            postgresql_where=text("status IN ('draft','active')"),
            sqlite_where=text("status IN ('draft','active')"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(4))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    custom_caption: Mapped[str | None] = mapped_column(Text)
    pdf_file_id: Mapped[str] = mapped_column(Text)
    pdf_path: Mapped[str] = mapped_column(Text)
    preview_file_id: Mapped[str | None] = mapped_column(Text)
    questions_count: Mapped[int] = mapped_column(Integer)
    answer_key: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    referral_required: Mapped[bool] = mapped_column(default=False)
    referral_count: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=1)
    prizes_count: Mapped[int] = mapped_column(default=0)
    show_key_after_close: Mapped[bool] = mapped_column(default=False)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"))
    channel_post_id: Mapped[int | None] = mapped_column(BigInteger)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    results_published: Mapped[bool] = mapped_column(default=False)


class Submission(Base):
    """One scored attempt."""

    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("test_id", "user_id", "attempt_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    attempt_no: Mapped[int] = mapped_column(default=1)
    answers: Mapped[dict] = mapped_column(JSON)
    correct_count: Mapped[int] = mapped_column(Integer)
    wrong_count: Mapped[int] = mapped_column(Integer)
    score_percent: Mapped[float] = mapped_column(Float)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    rank: Mapped[int | None] = mapped_column(Integer)


class Referral(Base):
    """Unique invitation attributed once."""

    __tablename__ = "referrals"
    __table_args__ = (CheckConstraint("inviter_id != invited_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invited_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    test_id: Mapped[int | None] = mapped_column(ForeignKey("tests.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_valid: Mapped[bool] = mapped_column(default=False)


class AccessLog(Base):
    """Unique test download record."""

    __tablename__ = "test_access_log"
    __table_args__ = (UniqueConstraint("test_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    got_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Admin(Base):
    """Role based administrator."""

    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    role: Mapped[str] = mapped_column(String(16))
    added_by: Mapped[int | None] = mapped_column(BigInteger)


class Broadcast(Base):
    """Resumable broadcast configuration."""

    __tablename__ = "broadcasts"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    media_file_id: Mapped[str | None] = mapped_column(Text)
    button_text: Mapped[str | None] = mapped_column(String(64))
    button_url: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(32), default="all")
    test_id: Mapped[int | None] = mapped_column(ForeignKey("tests.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    total: Mapped[int] = mapped_column(default=0)
    sent: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    cursor: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    """Global settings."""

    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Delivery(Base):
    """Persistent notification deduplication."""

    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
