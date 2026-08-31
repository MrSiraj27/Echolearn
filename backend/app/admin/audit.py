import uuid

from sqlalchemy.orm import Session

from app.models import AdminAuditLog


def log_admin_action(
    db: Session,
    admin_user_id: uuid.UUID | None,
    action: str,
    target_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Write one row to the append-only admin audit trail. Called inline (not
    deferred/async) so the log entry commits atomically with the action it records."""
    db.add(
        AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_id=target_id,
            details=details,
            ip_address=ip_address,
        )
    )
