from datetime import UTC, datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uid():
    return str(uuid4())


def now():
    return int(datetime.now(UTC).timestamp())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(default=now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    access_hash: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    access_expires: Mapped[int]
    refresh_expires: Mapped[int]


class ResetToken(Base):
    __tablename__ = "reset_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires: Mapped[int]


class Mail(Base):
    __tablename__ = "mail_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipient: Mapped[str] = mapped_column(String(254))
    body: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[int] = mapped_column(default=now)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(default=1)
    expires: Mapped[int]


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key"),
        ForeignKeyConstraint(
            ["chart_id", "user_id"],
            ["birth_charts.id", "birth_charts.user_id"],
            name="fk_reading_chart_owner",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    chart_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(20))
    question: Mapped[str] = mapped_column(Text)
    facts: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[int] = mapped_column(default=now, index=True)


class BirthChart(Base):
    __tablename__ = "birth_charts"
    __table_args__ = (UniqueConstraint("id", "user_id", name="uq_birth_chart_owner"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    birth_input: Mapped[dict] = mapped_column(JSON)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(default=now)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("reading_id", "idempotency_key"),
        UniqueConstraint("reading_id", "sequence", name="uq_message_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reading_id: Mapped[str] = mapped_column(
        ForeignKey("readings.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    question: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[int] = mapped_column(default=now)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("reading_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reading_id: Mapped[str] = mapped_column(ForeignKey("readings.id", ondelete="CASCADE"))
    note: Mapped[str] = mapped_column(Text, default="")
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[int] = mapped_column(default=now)


class UsageBucket(Base):
    __tablename__ = "usage_buckets"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reading_id: Mapped[str] = mapped_column(
        ForeignKey("readings.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[int] = mapped_column(default=now, index=True)
    last_error: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lease_until: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[int] = mapped_column(default=now)


class Event(Base):
    __tablename__ = "reading_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reading_id: Mapped[str] = mapped_column(
        ForeignKey("readings.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(default=now)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("source_key", "version", name="uq_document_source_version"),
        Index(
            "uq_document_active_source",
            "source_key",
            unique=True,
            postgresql_where=text("active = true"),
            sqlite_where=text("active = 1"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(30))
    license: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(20), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(default=now)
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", passive_deletes=True)


class Chunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    tags: Mapped[list] = mapped_column(JSON)
    content: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")


class GenerationRun(Base):
    __tablename__ = "generation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reading_id: Mapped[str] = mapped_column(
        ForeignKey("readings.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="completed")
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_mode: Mapped[str] = mapped_column(String(20), default="metadata")
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    source_ids: Mapped[list] = mapped_column(JSON)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    calls: Mapped[int] = mapped_column(default=0)
    trace: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(default=now)
