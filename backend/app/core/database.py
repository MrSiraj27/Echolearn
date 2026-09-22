from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# pool_pre_ping + pool_recycle: a managed Postgres that scales to zero when idle (e.g. Neon)
# can silently drop connections sitting in the pool; without these, the next request after
# an idle period fails with "server closed the connection unexpectedly" instead of
# transparently reconnecting. Harmless against an always-on local Postgres too.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
