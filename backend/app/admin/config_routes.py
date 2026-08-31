from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.admin.audit import log_admin_action
from app.admin.config_service import DEFAULT_CONFIG, get_config, refresh_config, set_config_value
from app.core.database import get_db
from app.core.security import get_current_admin, require_role
from app.models import User

router = APIRouter(prefix="/admin/config", tags=["admin-config"], dependencies=[Depends(get_current_admin)])


class UpdateConfigRequest(BaseModel):
    key: str
    value: dict


@router.get("/")
def get_all_config(admin: User = Depends(require_role("superadmin", "support", "moderator"))):
    return get_config()


@router.patch("/", status_code=status.HTTP_204_NO_CONTENT)
def update_config(
    payload: UpdateConfigRequest,
    request: Request,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
):
    if payload.key not in DEFAULT_CONFIG:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown config key: {payload.key}")

    before = get_config().get(payload.key)
    set_config_value(db, payload.key, payload.value, admin.id)
    log_admin_action(
        db,
        admin.id,
        "config.update",
        target_id=payload.key,
        details={"before": before, "after": payload.value},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    refresh_config(db)
