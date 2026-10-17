"""Finish queue recovery, usage accounting, message ordering and vector provenance."""

from collections import defaultdict

import sqlalchemy as sa
from alembic import context, op

revision = "0004_release_flows"
down_revision = "0003_document_chart_links"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("0004 contains a data backfill and must run online")
    op.create_table(
        "usage_buckets",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("day", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.add_column("messages", sa.Column("sequence", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("error_code", sa.String(50), nullable=True))
    op.add_column(
        "jobs", sa.Column("available_at", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("jobs", sa.Column("last_error", sa.String(50), nullable=True))
    op.create_index("ix_jobs_available_at", "jobs", ["available_at"])
    op.add_column("knowledge_chunks", sa.Column("embedding_model", sa.String(100), nullable=True))
    op.add_column("generation_runs", sa.Column("message_id", sa.String(36), nullable=True))
    op.add_column(
        "generation_runs",
        sa.Column("status", sa.String(20), nullable=False, server_default="legacy"),
    )
    op.add_column("generation_runs", sa.Column("error_code", sa.String(50), nullable=True))
    op.add_column("generation_runs", sa.Column("embedding_model", sa.String(100), nullable=True))
    op.add_column(
        "generation_runs",
        sa.Column("embedding_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_runs",
        sa.Column("retrieval_mode", sa.String(20), nullable=False, server_default="unknown"),
    )
    with op.batch_alter_table("generation_runs") as batch:
        batch.create_foreign_key(
            "fk_generation_message", "messages", ["message_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_index("ix_generation_runs_message_id", ["message_id"])
    db = op.get_bind()
    messages = sa.table(
        "messages",
        sa.column("id"),
        sa.column("reading_id"),
        sa.column("sequence"),
        sa.column("created_at"),
    )
    sequences = defaultdict(int)
    for row in db.execute(sa.select(messages).order_by(messages.c.created_at, messages.c.id)):
        sequences[row.reading_id] += 1
        db.execute(
            messages.update()
            .where(messages.c.id == row.id)
            .values(sequence=sequences[row.reading_id])
        )
    with op.batch_alter_table("messages") as batch:
        batch.alter_column("sequence", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint("uq_message_sequence", ["reading_id", "sequence"])
    readings = sa.table("readings", sa.column("id"), sa.column("user_id"), sa.column("created_at"))
    charts = sa.table("birth_charts", sa.column("user_id"), sa.column("created_at"))
    usage = defaultdict(int)
    for table, kind in [(readings, "reading"), (charts, "chart")]:
        for row in db.execute(sa.select(table.c.user_id, table.c.created_at)):
            usage[(row.user_id, row.created_at // 86400, kind)] += 1
    for row in db.execute(
        sa.select(readings.c.user_id, messages.c.created_at).select_from(
            messages.join(readings, messages.c.reading_id == readings.c.id)
        )
    ):
        usage[(row.user_id, row.created_at // 86400, "message")] += 1
    table = sa.table("usage_buckets", *[sa.column(x) for x in ("user_id", "day", "kind", "count")])
    if usage:
        db.execute(
            table.insert(),
            [
                dict(user_id=user, day=day, kind=kind, count=count)
                for (user, day, kind), count in usage.items()
            ],
        )


def downgrade():
    with op.batch_alter_table("generation_runs") as batch:
        batch.drop_constraint("fk_generation_message", type_="foreignkey")
        batch.drop_index("ix_generation_runs_message_id")
        for name in (
            "message_id",
            "status",
            "error_code",
            "embedding_model",
            "embedding_tokens",
            "retrieval_mode",
        ):
            batch.drop_column(name)
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("uq_message_sequence", type_="unique")
        batch.drop_column("sequence")
        batch.drop_column("error_code")
    op.drop_index("ix_jobs_available_at", table_name="jobs")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("available_at")
        batch.drop_column("last_error")
    with op.batch_alter_table("knowledge_chunks") as batch:
        batch.drop_column("embedding_model")
    op.drop_table("usage_buckets")
