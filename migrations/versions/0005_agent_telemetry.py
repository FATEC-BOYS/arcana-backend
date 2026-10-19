"""Record privacy-safe LangGraph stage timings and review decisions."""

import sqlalchemy as sa
from alembic import op

revision = "0005_agent_telemetry"
down_revision = "0004_release_flows"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "generation_runs",
        sa.Column(
            "trace",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade():
    op.drop_column("generation_runs", "trace")
