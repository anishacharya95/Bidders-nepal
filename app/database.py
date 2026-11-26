from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}

# Small pool suitable for a single free Render instance in front of Postgres.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
    **(
        {}
        if _is_sqlite
        else {"pool_size": 5, "max_overflow": 5, "pool_recycle": 280, "pool_timeout": 30}
    ),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Read-only reporting engine used when the API runs SQLite (local demos/tests).
# Postgres deployments use the primary engine.
reporting_engine = engine


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
