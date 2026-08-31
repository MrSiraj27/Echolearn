from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.limits import get_effective_limits
from app.core.security import get_current_user
from app.core.usage import rolling_quota_usage
from app.models import Document, Plan, User, Workspace
from app.users.schemas import MyUsageResponse, PublicPlan, QuotaUsageItem

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/plans", response_model=list[PublicPlan])
def list_public_plans(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Plan tiers for the in-app upgrade page — any authenticated user can see pricing,
    not just admins."""
    return db.query(Plan).order_by(Plan.price_monthly.asc().nulls_last()).all()


@router.get("/me/usage", response_model=MyUsageResponse)
def get_my_usage(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    effective = get_effective_limits(current_user)

    quotas = [QuotaUsageItem(**item) for item in rolling_quota_usage(db, current_user)]

    doc_count = db.query(Document).filter(Document.user_id == current_user.id).count()
    workspace_count = db.query(Workspace).filter(Workspace.user_id == current_user.id).count()
    quotas.append(
        QuotaUsageItem(key="max_documents", label="Documents", limit=effective.get("max_documents"), current_usage=doc_count)
    )
    quotas.append(
        QuotaUsageItem(
            key="max_workspaces", label="Workspaces", limit=effective.get("max_workspaces"), current_usage=workspace_count
        )
    )

    return MyUsageResponse(
        plan_id=current_user.plan_id,
        plan_name=current_user.plan.name if current_user.plan else None,
        quotas=quotas,
    )
