import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.admin.audit import log_admin_action
from app.admin.plans_schemas import CreatePlanRequest, PlanResponse, UpdatePlanRequest
from app.core.database import get_db
from app.core.security import get_current_admin, require_role
from app.models import Plan, User

router = APIRouter(prefix="/admin/plans", tags=["admin-plans"], dependencies=[Depends(get_current_admin)])


def _get_plan_or_404(db: Session, plan_id: uuid.UUID) -> Plan:
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    return plan


@router.get("", response_model=list[PlanResponse])
@router.get("/", response_model=list[PlanResponse], include_in_schema=False)
def list_plans(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return db.query(Plan).order_by(Plan.created_at.asc()).all()


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PlanResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_plan(
    payload: CreatePlanRequest,
    request: Request,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
):
    existing = db.query(Plan).filter(Plan.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A plan with this slug already exists.")

    if payload.is_default:
        db.query(Plan).filter(Plan.is_default.is_(True)).update({"is_default": False})

    plan = Plan(
        name=payload.name,
        slug=payload.slug,
        is_default=payload.is_default,
        limits=payload.limits.model_dump(),
        price_monthly=payload.price_monthly,
    )
    db.add(plan)
    db.flush()

    log_admin_action(
        db,
        admin.id,
        "plan.create",
        target_id=str(plan.id),
        details={"name": plan.name, "slug": plan.slug},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: uuid.UUID,
    payload: UpdatePlanRequest,
    request: Request,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
):
    plan = _get_plan_or_404(db, plan_id)

    if payload.name is not None:
        plan.name = payload.name
    if payload.limits is not None:
        plan.limits = payload.limits.model_dump()
    if payload.price_monthly is not None:
        plan.price_monthly = payload.price_monthly
    if payload.is_default is not None:
        if payload.is_default:
            db.query(Plan).filter(Plan.id != plan.id).update({"is_default": False})
        plan.is_default = payload.is_default

    log_admin_action(
        db,
        admin.id,
        "plan.update",
        target_id=str(plan.id),
        details={"limits": plan.limits, "price_monthly": plan.price_monthly, "is_default": plan.is_default},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(plan)
    return plan
