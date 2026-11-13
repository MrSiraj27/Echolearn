"""Allowed state transitions for study plans and their sessions.

    StudySession.status:  pending -> completed | skipped        (both final)
    StudyPlan.status:     active  -> completed                  (no pending sessions left)
                          active  -> abandoned                  (user deletes the plan)

Sessions can only change while their plan is active. Every writer (the plan routes and
the quiz auto-complete) goes through here so the rules live in one place.
"""

from datetime import datetime, timezone

from app.models import StudyPlan, StudyPlanStatus, StudySession, StudySessionStatus


class TransitionError(Exception):
    """The requested change isn't allowed from the current state."""


def resolve_session(plan: StudyPlan, session: StudySession, target: StudySessionStatus) -> bool:
    """Move a pending session to completed/skipped and complete the plan if nothing is left.

    Returns False (and changes nothing) when the session is already in `target`, so a
    repeated click is harmless. Raises TransitionError for any other illegal change."""
    if target not in (StudySessionStatus.completed, StudySessionStatus.skipped):
        raise TransitionError(f"Can't move a session to {target.value}.")
    if session.status == target:
        return False
    if plan.status != StudyPlanStatus.active:
        raise TransitionError(f"This study plan is {plan.status.value}, so its sessions can't be changed.")
    if session.status != StudySessionStatus.pending:
        raise TransitionError(f"This session is already {session.status.value}.")

    session.status = target
    session.completed_at = datetime.now(timezone.utc) if target == StudySessionStatus.completed else None
    complete_plan_if_done(plan)
    return True


def complete_plan_if_done(plan: StudyPlan) -> bool:
    """active -> completed once no session is still pending."""
    if plan.status != StudyPlanStatus.active:
        return False
    if any(s.status == StudySessionStatus.pending for s in plan.sessions):
        return False
    plan.status = StudyPlanStatus.completed
    return True


def require_active(plan: StudyPlan) -> None:
    if plan.status != StudyPlanStatus.active:
        raise TransitionError(f"This study plan is {plan.status.value}.")
