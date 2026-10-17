from alembic import context

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_engine

# Import domain models here once implemented so autogenerate can discover them.
target_metadata = Base.metadata

if context.is_offline_mode():
    from app.core.config import get_settings

    context.configure(
        url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
