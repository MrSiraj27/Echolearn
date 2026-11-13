"""Core behaviour tests for EchoLearn's backend.

These tests are deliberately side-effect free: they never create accounts, never send email
and never write to the database or the vector store. Pure logic is tested in-process; the HTTP
checks only call endpoints that are rejected before any state changes, and are skipped when no
server is listening on localhost:8000.

Run from the backend folder:  python -m unittest discover -s tests -v
"""
import json
import time
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from jose import jwt

from app.core.config import settings
from app.core.limits import LIMITS_SCHEMA_DEFAULTS, get_effective_limits
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.rag.chunking import chunk_text, clean_text
from app.rag.retrieval import (
    _Index,
    _continuation,
    _find_references,
    extract_page_numbers,
    extract_reference_numbers,
    normalize_query,
    tokenize,
)
from app.rag.smalltalk import detect_smalltalk_reply
from app.study.spaced_repetition import MIN_EASE_FACTOR, update_card_after_review

BASE_URL = "http://localhost:8000"


def _http(method: str, path: str, body: dict | None = None, headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def _server_up() -> bool:
    try:
        return _http("GET", "/health")[0] == 200
    except Exception:
        return False


def _chunk(text, page, doc="doc-1", user="u-1"):
    return {"text": text, "metadata": {"document_id": doc, "user_id": user, "page_number": page, "filename": "book.pdf"}}


# --------------------------------------------------------------------------- authentication
class AuthSecurityTests(unittest.TestCase):
    def test_AUTH01_password_round_trip(self):
        hashed = hash_password("correct horse battery")
        self.assertTrue(verify_password("correct horse battery", hashed))

    def test_AUTH02_wrong_password_rejected(self):
        hashed = hash_password("correct horse battery")
        self.assertFalse(verify_password("wrong password", hashed))

    def test_AUTH03_hash_is_salted_and_never_plaintext(self):
        a, b = hash_password("same-password"), hash_password("same-password")
        self.assertNotEqual(a, b)
        self.assertNotIn("same-password", a)
        self.assertTrue(a.startswith("$2"))  # bcrypt

    def test_AUTH04_access_token_carries_identity_and_type(self):
        uid = uuid.uuid4()
        payload = decode_token(create_access_token(uid, "a@b.test"))
        self.assertEqual(payload["sub"], str(uid))
        self.assertEqual(payload["type"], "access")

    def test_AUTH05_access_token_lifetime_matches_setting(self):
        payload = decode_token(create_access_token(uuid.uuid4(), "a@b.test"))
        lifetime = payload["exp"] - time.time()
        self.assertLessEqual(lifetime, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 5)
        self.assertGreater(lifetime, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 - 30)

    def test_AUTH06_refresh_token_is_marked_refresh(self):
        self.assertEqual(decode_token(create_refresh_token(uuid.uuid4()))["type"], "refresh")

    def test_AUTH07_tampered_token_rejected(self):
        token = create_access_token(uuid.uuid4(), "a@b.test")
        broken = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        with self.assertRaises(Exception) as ctx:
            decode_token(broken)
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)

    def test_AUTH08_expired_token_rejected(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = jwt.encode(
            {"sub": str(uuid.uuid4()), "exp": past, "type": "access"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
        )
        with self.assertRaises(Exception) as ctx:
            decode_token(token)
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)

    def test_AUTH09_token_signed_with_other_secret_rejected(self):
        forged = jwt.encode(
            {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(minutes=5), "type": "access"},
            "not-the-real-secret",
            algorithm=settings.JWT_ALGORITHM,
        )
        with self.assertRaises(Exception):
            decode_token(forged)

    def test_AUTH10_rate_limiter_blocks_sixth_attempt(self):
        key = f"test-limit:{uuid.uuid4()}"
        for _ in range(5):
            check_rate_limit(key)
        with self.assertRaises(Exception) as ctx:
            check_rate_limit(key)
        self.assertEqual(getattr(ctx.exception, "status_code", None), 429)


# --------------------------------------------------------------------------- quotas
class PlanLimitTests(unittest.TestCase):
    def _user(self, plan_limits=None, custom=None):
        return SimpleNamespace(plan=SimpleNamespace(limits=plan_limits) if plan_limits is not None else None, custom_limits=custom)

    def test_LIM01_defaults_apply_without_plan(self):
        limits = get_effective_limits(self._user())
        self.assertEqual(limits["message_window_hours"], LIMITS_SCHEMA_DEFAULTS["message_window_hours"])

    def test_LIM02_plan_values_override_defaults(self):
        limits = get_effective_limits(self._user({"max_documents": 5, "messages_per_window": 30}))
        self.assertEqual(limits["max_documents"], 5)
        self.assertEqual(limits["messages_per_window"], 30)

    def test_LIM03_custom_limit_overrides_plan(self):
        limits = get_effective_limits(self._user({"max_documents": 5}, {"max_documents": 50}))
        self.assertEqual(limits["max_documents"], 50)

    def test_LIM04_explicit_none_means_unlimited(self):
        limits = get_effective_limits(self._user({"max_documents": 5}, {"max_documents": None}))
        self.assertIsNone(limits["max_documents"])


# --------------------------------------------------------------------------- spaced repetition
class SpacedRepetitionTests(unittest.TestCase):
    def _card(self):
        return SimpleNamespace(
            ease_factor=2.5, interval_days=0, repetitions=0, next_review_date=None, last_reviewed_at=None
        )

    def test_SR01_first_two_successes_use_1_then_6_days(self):
        card = self._card()
        update_card_after_review(card, 5)
        self.assertEqual(card.interval_days, 1)
        update_card_after_review(card, 5)
        self.assertEqual(card.interval_days, 6)

    def test_SR02_third_success_multiplies_by_ease(self):
        card = self._card()
        for _ in range(2):
            update_card_after_review(card, 5)
        ease_before = card.ease_factor
        update_card_after_review(card, 5)
        self.assertEqual(card.interval_days, round(6 * ease_before))

    def test_SR03_failure_resets_repetitions_and_interval(self):
        card = self._card()
        for _ in range(3):
            update_card_after_review(card, 5)
        update_card_after_review(card, 1)
        self.assertEqual(card.repetitions, 0)
        self.assertEqual(card.interval_days, 1)

    def test_SR04_ease_factor_never_below_floor(self):
        card = self._card()
        for _ in range(30):
            update_card_after_review(card, 0)
        self.assertGreaterEqual(card.ease_factor, MIN_EASE_FACTOR)

    def test_SR05_next_review_date_is_in_the_future(self):
        card = self._card()
        update_card_after_review(card, 3)
        self.assertGreater(card.next_review_date, date.today() - timedelta(days=1))
        self.assertEqual(card.next_review_date, date.today() + timedelta(days=card.interval_days))


# --------------------------------------------------------------------------- chunking
class ChunkingTests(unittest.TestCase):
    DOC, USER = uuid.uuid4(), uuid.uuid4()

    def test_CH01_chunks_respect_size_limit(self):
        text = ("This is a sentence about cellular respiration and ATP. " * 120).strip()
        chunks = chunk_text([{"page_number": 1, "text": text, "tables": []}], self.DOC, self.USER, "bio.pdf")
        self.assertGreater(len(chunks), 3)
        self.assertTrue(all(len(c["text"]) <= 1100 for c in chunks))

    def test_CH02_every_chunk_keeps_page_and_filename(self):
        pages = [{"page_number": n, "text": f"Page {n} text. " * 40, "tables": []} for n in (1, 2)]
        chunks = chunk_text(pages, self.DOC, self.USER, "bio.pdf")
        self.assertEqual({c["metadata"]["page_number"] for c in chunks}, {1, 2})
        self.assertTrue(all(c["metadata"]["filename"] == "bio.pdf" for c in chunks))

    def test_CH03_table_stays_one_chunk(self):
        table = {"markdown_table": "| a | b |\n|---|---|\n| 1 | 2 |", "json_table": [["a", "b"], ["1", "2"]], "table_index": 0}
        chunks = chunk_text([{"page_number": 1, "text": "", "tables": [table]}], self.DOC, self.USER, "t.pdf")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["metadata"]["chunk_type"], "table")

    def test_CH04_transcript_chunks_carry_timestamps(self):
        pages = [{"page_number": i, "text": "word " * 60, "tables": [], "start_time": i * 5.0, "end_time": i * 5.0 + 5}
                 for i in range(1, 8)]
        chunks = chunk_text(pages, self.DOC, self.USER, "lecture.mp3")
        self.assertTrue(all("start_time_seconds" in c["metadata"] for c in chunks))
        self.assertLess(chunks[0]["metadata"]["start_time_seconds"], chunks[0]["metadata"]["end_time_seconds"])

    def test_CH05_cleaning_removes_glyph_placeholders_and_footer_urls(self):
        dirty = "The Book Of Faith(cid:9) 167\nhttp://islamicbookshub.wordpress.com/\nreal sentence here"
        cleaned = clean_text(dirty)
        self.assertNotIn("(cid:", cleaned)
        self.assertNotIn("http", cleaned)
        self.assertIn("real sentence here", cleaned)


# --------------------------------------------------------------------------- retrieval helpers
class RetrievalTests(unittest.TestCase):
    def test_RET01_spelling_variants_are_normalised(self):
        self.assertEqual(normalize_query("tell me about 240 hadees"), "tell me about 240 hadith")

    def test_RET02_reference_number_needs_a_reference_word(self):
        self.assertEqual(extract_reference_numbers("tell me about 240 hadees"), ["240"])
        self.assertEqual(extract_reference_numbers("what is hadith no. 1663?"), ["1663"])
        self.assertEqual(extract_reference_numbers("top 5 reasons to study"), [])

    def test_RET03_page_numbers_extracted(self):
        self.assertEqual(extract_page_numbers("explain page 168"), [168])
        self.assertEqual(extract_page_numbers("summarise this"), [])

    def test_RET04_tokeniser_drops_stopwords_and_noise(self):
        self.assertEqual(tokenize("What is the (cid:9) ruling on Wudu?"), ["ruling", "wudu"])

    def test_RET05_bm25_ranks_exact_number_first(self):
        chunks = [_chunk("A general passage about prayer and fasting in Ramadan.", 1),
                  _chunk("[240] 131 - (78) It was narrated that Zirr said: Ali said", 2),
                  _chunk("Another passage about charity and the poor.", 3)]
        idx = _Index(chunks)
        ranked = idx.bm25(tokenize("hadith 240"), limit=3)
        self.assertEqual(ranked[0][0], 1)

    def test_RET06_bracketed_marker_is_primary_other_numbering_is_secondary(self):
        chunks = [_chunk("[240] 131 - (78) first item", 168),
                  _chunk("[386] 240 - (153) a different numbering of the same count", 244),
                  _chunk("nothing relevant", 9)]
        primary, secondary = _find_references(_Index(chunks), ["240"])
        self.assertEqual(primary, [0])
        self.assertEqual(secondary, [1])

    def test_RET07_continuation_follows_into_next_page(self):
        chunks = [_chunk("[240] 131 - (78) Ali said: By the One Who split the seed and", 168),
                  _chunk("created the soul, the unlettered Prophet affirmed to me", 169),
                  _chunk("unrelated page", 170)]
        idx = _Index(chunks)
        self.assertEqual(_continuation(idx, 0), [1])


class SmalltalkTests(unittest.TestCase):
    def test_ST01_greeting_gets_a_reply_without_retrieval(self):
        self.assertIsNotNone(detect_smalltalk_reply("hello"))

    def test_ST02_real_question_is_not_smalltalk(self):
        self.assertIsNone(detect_smalltalk_reply("What is the function of mitochondria?"))


# --------------------------------------------------------------------------- HTTP (live server)
@unittest.skipUnless(_server_up(), "backend not running on localhost:8000")
class ApiContractTests(unittest.TestCase):
    def test_API01_health_endpoint(self):
        status, body = _http("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

    def test_API02_protected_routes_reject_missing_token(self):
        for path in ("/chats/", "/documents/", "/folders/", "/quizzes/", "/users/me/usage"):
            with self.subTest(path=path):
                self.assertEqual(_http("GET", path)[0], 401)

    def test_API03_garbage_token_rejected(self):
        status, _ = _http("GET", "/documents/", headers={"Authorization": "Bearer not.a.token"})
        self.assertEqual(status, 401)

    def test_API04_admin_routes_reject_missing_token(self):
        self.assertIn(_http("GET", "/admin/users/")[0], (401, 403))

    def test_API05_signup_rejects_invalid_email(self):
        status, _ = _http("POST", "/auth/signup", {"name": "T", "email": "not-an-email", "password": "longenough1"})
        self.assertEqual(status, 422)

    def test_API06_signup_rejects_short_password(self):
        status, _ = _http("POST", "/auth/signup", {"name": "T", "email": "someone@example.com", "password": "short"})
        self.assertEqual(status, 422)

    def test_API07_login_unknown_account_is_generic_401(self):
        status, body = _http("POST", "/auth/login", {"email": f"nobody-{uuid.uuid4().hex[:8]}@example.com", "password": "whatever123"})
        self.assertEqual(status, 401)
        self.assertNotIn("not found", body.lower())

    def test_API08_openapi_schema_published(self):
        status, body = _http("GET", "/openapi.json")
        self.assertEqual(status, 200)
        self.assertGreater(len(json.loads(body)["paths"]), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
