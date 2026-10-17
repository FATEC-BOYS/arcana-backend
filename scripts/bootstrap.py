from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.rag.seed import seed_knowledge


def main():
    command.upgrade(Config("alembic.ini"), "head")
    with Session(get_engine()) as db:
        seed_knowledge(db)


if __name__ == "__main__":
    main()
