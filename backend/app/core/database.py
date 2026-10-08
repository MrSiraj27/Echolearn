from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# pool_pre_ping + pool_recycle: a managed Postgres that scales to zero when idle (e.g. Neon)
# can silently drop connections sitting in the pool; without these, the next request after
# an idle period fails with "server closed the connection unexpectedly" instead of
# transparently reconnecting. Harmless against an always-on local Postgres too.
# connect_timeout: without it a stalled connection to the database blocks forever, and since
# startup runs migrations first, the whole API never comes up (every request then 503s).
# (connect_timeout is a Postgres/psycopg2 option; other databases would reject it.)
_connect_args = {"connect_timeout": 20} if settings.DATABASE_URL.startswith("postgres") else {}
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
