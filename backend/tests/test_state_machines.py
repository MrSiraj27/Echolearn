"""Transition guards for the app's status fields (study plans/sessions, moderation reports,
admin document retry). Side-effect free: plain objects and a fake DB session, no database.

Run from the backend folder:  python -m unittest discover -s tests -v
"""
import unittest
import uuid
from types import SimpleNamespace

from fastapi import HTTPException

from app.admin.moderation_routes import action_report
from app.admin.system_routes import retry_document_processing
from app.models import DocumentStatus, StudyPlanStatus, StudySessionStatus
from app.study.lifecycle import TransitionError, complete_plan_if_done, require_active, resolve_session


def _plan(*session_statuses, status=StudyPlanStatus.active):
    sessions = [SimpleNamespace(status=s, completed_at=None) for s in session_statuses]
    return SimpleNamespace(status=status, sessions=sessions)


class StudySessionTransitions(unittest.TestCase):
    def test_complete_pending_sets_timestamp(self):
        plan = _plan(StudySessionStatus.pending, StudySessionStatus.pending)
        s = plan.sessions[0]
        self.assertTrue(resolve_session(plan, s, StudySessionStatus.completed))
        self.assertEqual(s.status, StudySessionStatus.completed)
        self.assertIsNotNone(s.completed_at)
        self.assertEqual(plan.status, StudyPlanStatus.active)  # one still pending

    def test_skip_pending_has_no_timestamp(self):
        plan = _plan(StudySessionStatus.pending, StudySessionStatus.pending)
        resolve_session(plan, plan.sessions[0], StudySessionStatus.skipped)
        self.assertIsNone(plan.sessions[0].completed_at)

    def test_same_target_is_a_noop(self):
        plan = _plan(StudySessionStatus.completed, StudySessionStatus.pending)
        self.assertFalse(resolve_session(plan, plan.sessions[0], StudySessionStatus.completed))

    def test_completed_cannot_be_skipped_and_vice_versa(self):
        plan = _plan(StudySessionStatus.completed, StudySessionStatus.skipped, StudySessionStatus.pending)
        with self.assertRaises(TransitionError):
            resolve_session(plan, plan.sessions[0], StudySessionStatus.skipped)
        with self.assertRaises(TransitionError):
            resolve_session(plan, plan.sessions[1], StudySessionStatus.completed)

    def test_cannot_reopen_a_session(self):
        plan = _plan(StudySessionStatus.completed)
        with self.assertRaises(TransitionError):
            resolve_session(plan, plan.sessions[0], StudySessionStatus.pending)

    def test_sessions_of_abandoned_plan_are_frozen(self):
        plan = _plan(StudySessionStatus.pending, status=StudyPlanStatus.abandoned)
        with self.assertRaises(TransitionError):
            resolve_session(plan, plan.sessions[0], StudySessionStatus.completed)
        self.assertEqual(plan.sessions[0].status, StudySessionStatus.pending)

    def test_last_pending_session_completes_the_plan(self):
        plan = _plan(StudySessionStatus.skipped, StudySessionStatus.pending)
        resolve_session(plan, plan.sessions[1], StudySessionStatus.completed)
        self.assertEqual(plan.status, StudyPlanStatus.completed)

    def test_skipping_the_last_session_also_completes_the_plan(self):
        plan = _plan(StudySessionStatus.completed, StudySessionStatus.pending)
        resolve_session(plan, plan.sessions[1], StudySessionStatus.skipped)
        self.assertEqual(plan.status, StudyPlanStatus.completed)

    def test_abandoned_plan_never_becomes_completed(self):
        plan = _plan(StudySessionStatus.completed, status=StudyPlanStatus.abandoned)
        self.assertFalse(complete_plan_if_done(plan))
        self.assertEqual(plan.status, StudyPlanStatus.abandoned)

    def test_require_active(self):
        require_active(_plan())
        with self.assertRaises(TransitionError):
            require_active(_plan(status=StudyPlanStatus.completed))


class _FakeQuery:
    def __init__(self, row):
        self.row = row

    def filter(self, *a, **k):
        return self

    def first(self):
        return self.row


class _FakeDB:
    """Returns `row` for every query; fails the test if anything is written."""

    def __init__(self, row):
        self.row = row

    def query(self, *a):
        return _FakeQuery(self.row)

    def _forbidden(self, *a, **k):
        raise AssertionError("route wrote to the database despite rejecting the transition")

    add = delete = commit = _forbidden


class ModerationReportTransitions(unittest.TestCase):
    def test_resolved_reports_cannot_be_resolved_again(self):
        for current in ("dismissed", "actioned"):
            for action in ("dismiss", "remove_document", "suspend_user"):
                report = SimpleNamespace(id=uuid.uuid4(), status=current, document_id=uuid.uuid4())
                with self.assertRaises(HTTPException) as ctx:
                    action_report(
                        report_id=report.id,
                        payload=SimpleNamespace(action=action),
                        request=SimpleNamespace(client=None),
                        admin=SimpleNamespace(id=uuid.uuid4()),
                        db=_FakeDB(report),
                    )
                self.assertEqual(ctx.exception.status_code, 409)
                self.assertEqual(report.status, current)


class AdminDocumentRetry(unittest.TestCase):
    def test_in_progress_documents_cannot_be_retried(self):
        for current in (DocumentStatus.uploaded, DocumentStatus.parsing, DocumentStatus.embedded):
            doc = SimpleNamespace(id=uuid.uuid4(), status=current)
            with self.assertRaises(HTTPException) as ctx:
                retry_document_processing(
                    document_id=doc.id,
                    request=SimpleNamespace(client=None),
                    background_tasks=None,
                    admin=SimpleNamespace(id=uuid.uuid4()),
                    db=_FakeDB(doc),
                )
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(doc.status, current)


if __name__ == "__main__":
    unittest.main()
