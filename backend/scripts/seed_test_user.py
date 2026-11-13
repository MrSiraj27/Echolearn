"""Create (or reset) a verified LOCAL test account for manually trying the app.

Refuses to run unless DATABASE_URL points at localhost, so it can never touch a real
deployment. The account below is a throwaway test value, not a real credential.

Usage (from the backend folder):
    python scripts/seed_test_user.py
"""
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User

TEST_EMAIL = "reader-test@example.com"
TEST_PASSWORD = "LocalTest-Reader-2026"
TEST_NAME = "Local Test User"


def main() -> None:
    host = urlparse(settings.DATABASE_URL).hostname
    if host not in ("localhost", "127.0.0.1", "::1"):
        print(f"Refusing to seed a test user into a non-local database ({host}).", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == TEST_EMAIL).first()
        if user:
            user.password_hash = hash_password(TEST_PASSWORD)
            user.is_verified = True
            user.is_blocked = False
            print(f"Reset local test user {TEST_EMAIL}.")
        else:
            db.add(User(name=TEST_NAME, email=TEST_EMAIL, password_hash=hash_password(TEST_PASSWORD), is_verified=True))
            print(f"Created local test user {TEST_EMAIL}.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
