"""Link natal readings to charts and normalize versioned knowledge documents.

Data migration: run online. Existing reading snapshots and chunk identifiers are retained.
"""

import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import context, op

revision = "0003_document_chart_links"
down_revision = "0002_domain"
branch_labels = None
depends_on = None


def _key(source, topic):
    return hashlib.sha256(json.dumps([source, topic]).encode()).hexdigest()


def _checksum(rows):
    contents = [{"content": x["content"], "tags": sorted(x["tags"])} for x in rows]
    return hashlib.sha256(
        json.dumps(contents, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _version_key(value):
    return [(1, int(x)) if x.isdigit() else (0, x) for x in re.split(r"(\d+)", value)]


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("0003 contains a data backfill and must run online")
    connection = op.get_bind()
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("license", sa.String(80), nullable=False),
        sa.Column("topic", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("source_key", "version", name="uq_document_source_version"),
    )
    op.create_index("ix_knowledge_documents_source_key", "knowledge_documents", ["source_key"])
    op.create_index("ix_knowledge_documents_topic", "knowledge_documents", ["topic"])
    op.add_column("knowledge_chunks", sa.Column("document_id", sa.String(36), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("chunk_index", sa.Integer(), nullable=True))
    documents = sa.table(
        "knowledge_documents",
        *[
            sa.column(x)
            for x in (
                "id",
                "source_key",
                "source",
                "version",
                "license",
                "topic",
                "content_hash",
                "active",
                "created_at",
            )
        ],
    )
    chunks = sa.table(
        "knowledge_chunks",
        sa.column("id"),
        sa.column("source"),
        sa.column("version"),
        sa.column("license"),
        sa.column("topic"),
        sa.column("content"),
        sa.column("tags", sa.JSON()),
        sa.column("document_id"),
        sa.column("chunk_index"),
    )
    groups = {}
    for row in connection.execute(sa.select(chunks).order_by(chunks.c.id)).mappings():
        groups.setdefault((row["source"], row["topic"], row["version"]), []).append(dict(row))
    latest = {}
    for source, topic, version in groups:
        key = (source, topic)
        if key not in latest or _version_key(version) > _version_key(latest[key]):
            latest[key] = version
    for (source, topic, version), rows in groups.items():
        licenses = {x["license"] for x in rows}
        if len(licenses) != 1:
            raise RuntimeError(
                "Conflicting licenses in one legacy source/version; resolve before migration"
            )
        document_id = str(uuid4())
        connection.execute(
            documents.insert().values(
                id=document_id,
                source_key=_key(source, topic),
                source=source,
                version=version,
                license=next(iter(licenses)),
                topic=topic,
                content_hash=_checksum(rows),
                active=(latest[(source, topic)] == version),
                created_at=int(datetime.now(UTC).timestamp()),
            )
        )
        for index, row in enumerate(rows):
            connection.execute(
                chunks.update()
                .where(chunks.c.id == row["id"])
                .values(document_id=document_id, chunk_index=index)
            )
    op.create_index(
        "uq_document_active_source",
        "knowledge_documents",
        ["source_key"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        sqlite_where=sa.text("active = 1"),
    )
    with op.batch_alter_table("knowledge_chunks") as batch:
        batch.alter_column("document_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("chunk_index", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_chunk_document", "knowledge_documents", ["document_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_unique_constraint("uq_document_chunk", ["document_id", "chunk_index"])
        batch.create_index("ix_knowledge_chunks_document_id", ["document_id"])
        batch.drop_index("ix_knowledge_chunks_topic")
        for name in ("source", "version", "license", "topic"):
            batch.drop_column(name)
    with op.batch_alter_table("birth_charts") as batch:
        batch.create_unique_constraint("uq_birth_chart_owner", ["id", "user_id"])
    op.add_column("readings", sa.Column("chart_id", sa.String(36), nullable=True))
    readings = sa.table(
        "readings",
        sa.column("id"),
        sa.column("kind"),
        sa.column("user_id"),
        sa.column("facts", sa.JSON()),
        sa.column("chart_id"),
    )
    charts = sa.table("birth_charts", sa.column("id"), sa.column("user_id"))
    owners = {row.id: row.user_id for row in connection.execute(sa.select(charts))}
    for row in connection.execute(
        sa.select(readings).where(readings.c.kind == "astrology")
    ).mappings():
        chart_id = row["facts"].get("chart_id")
        if chart_id and owners.get(chart_id) == row["user_id"]:
            connection.execute(
                readings.update().where(readings.c.id == row["id"]).values(chart_id=chart_id)
            )
    with op.batch_alter_table("readings") as batch:
        batch.create_foreign_key(
            "fk_reading_chart_owner",
            "birth_charts",
            ["chart_id", "user_id"],
            ["id", "user_id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_readings_chart_id", ["chart_id"])


def downgrade():
    with op.batch_alter_table("readings") as batch:
        batch.drop_constraint("fk_reading_chart_owner", type_="foreignkey")
        batch.drop_index("ix_readings_chart_id")
        batch.drop_column("chart_id")
    with op.batch_alter_table("birth_charts") as batch:
        batch.drop_constraint("uq_birth_chart_owner", type_="unique")
    for name, type_ in [
        ("source", sa.Text()),
        ("version", sa.String(30)),
        ("license", sa.String(80)),
        ("topic", sa.String(20)),
    ]:
        op.add_column("knowledge_chunks", sa.Column(name, type_, nullable=True))
    connection = op.get_bind()
    chunks = sa.table(
        "knowledge_chunks",
        sa.column("document_id"),
        *[sa.column(x) for x in ("source", "version", "license", "topic")],
    )
    docs = sa.table(
        "knowledge_documents",
        *[sa.column(x) for x in ("id", "source", "version", "license", "topic")],
    )
    for row in connection.execute(sa.select(docs)).mappings():
        connection.execute(
            chunks.update()
            .where(chunks.c.document_id == row["id"])
            .values(**{x: row[x] for x in ("source", "version", "license", "topic")})
        )
    with op.batch_alter_table("knowledge_chunks") as batch:
        batch.drop_constraint("fk_chunk_document", type_="foreignkey")
        batch.drop_constraint("uq_document_chunk", type_="unique")
        batch.drop_index("ix_knowledge_chunks_document_id")
        batch.drop_column("document_id")
        batch.drop_column("chunk_index")
        batch.create_index("ix_knowledge_chunks_topic", ["topic"])
        for name, type_ in [
            ("source", sa.Text()),
            ("version", sa.String(30)),
            ("license", sa.String(80)),
            ("topic", sa.String(20)),
        ]:
            batch.alter_column(name, existing_type=type_, nullable=False)
    op.drop_table("knowledge_documents")
