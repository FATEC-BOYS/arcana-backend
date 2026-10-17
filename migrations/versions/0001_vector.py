"""Enable vector storage; domain tables follow in subsequent migrations."""

from alembic import op

revision = "0001_vector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade():
    # Shared extension intentionally retained; dropping it can destroy other vector columns.
    pass
