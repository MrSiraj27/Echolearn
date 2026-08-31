"""One-time CLI to promote an existing user to admin, or create a new admin user.

There is intentionally NO API route that can do this — the only way to create or
promote an admin is running this script with direct database/server access.

Usage:
    python scripts/create_admin.py user@example.com --role superadmin
    python scripts/create_admin.py newadmin@example.com --role support --name "Jane" --password "..."
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User

VALID_ROLES = {"superadmin", "support", "moderator"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an admin user.")
    parser.add_argument("email")
    parser.add_argument("--role", required=True, choices=sorted(VALID_ROLES))
    parser.add_argument("--name", default=None, help="Required only if the user doesn't already exist.")
    parser.add_argument("--password", default=None, help="Required only if the user doesn't already exist.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()

        if user:
            user.is_admin = True
            user.admin_role = args.role
            db.commit()
            print(f"Promoted existing user {args.email} to admin (role={args.role}).")
            return

        if not args.name or not args.password:
            print("User doesn't exist yet — --name and --password are required to create one.", file=sys.stderr)
            sys.exit(1)

        user = User(
            name=args.name,
            email=args.email,
            password_hash=hash_password(args.password),
            is_verified=True,
            is_admin=True,
            admin_role=args.role,
        )
        db.add(user)
        db.commit()
        print(f"Created new admin user {args.email} (role={args.role}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
