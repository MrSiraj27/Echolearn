import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from http import HTTPStatus

from app.admin.auth_routes import router as admin_auth_router
from app.admin.config_routes import router as admin_config_router
from app.admin.moderation_routes import router as admin_moderation_router
from app.admin.plans_routes import router as admin_plans_router
from app.admin.system_routes import router as admin_system_router
from app.admin.users_routes import router as admin_users_router
from app.analytics.routes import router as analytics_router
from app.auth.routes import router as auth_router
from app.core.config import settings
from app.chats.routes import router as chats_router
from app.documents.routes import router as documents_router
from app.folders.routes import router as folders_router
from app.practice.past_paper_routes import router as past_papers_router
from app.practice.paper_routes import router as practice_papers_router
from app.quizzes.routes import router as quizzes_router
from app.study.plan_routes import router as study_plans_router
from app.study.review_routes import review_cards_router, review_router
from app.users.routes import router as users_router
from app.voice.routes import router as voice_router
from app.workspaces.routes import router as workspaces_router
from app.documents.background import fail_interrupted_documents
from app.voice.clone_background import fail_interrupted_jobs
from app.voice.clone_model import load_clone_model, shutdown_clone_worker
from app.voice.clone_routes import router as voice_clone_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run Alembic migrations to head on startup. Idempotent (a no-op if already at
    head), so it's safe to run on every boot. This makes deploys portable to hosts that
    don't offer a separate "build command" step (e.g. Koyeb's buildpack, unlike Render's
    render.yaml buildCommand which already runs this explicitly too)."""
    import os

    from alembic import command
    from alembic.config import Config

    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        command.upgrade(cfg, "head")
        logger.info("Alembic migrations up to date.")
    except Exception:
        logger.exception("Startup migration failed — the app will still start, but the DB schema may be stale.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    # The default Piper voice used to load eagerly here ("so the first request isn't
    # slow"), same as every other voice already loads lazily on first use (see
    # app/voice/tts.py's synthesize_speech). Loading it costs ~130MB of RSS, which a
    # memory-constrained host (e.g. Render's free 512MB tier) can't spare at boot — so it
    # now loads lazily too, trading a slower first /voice/speak call for headroom.
    load_clone_model()  # only logs whether the isolated cloning worker is installed; it starts lazily
    fail_interrupted_jobs()
    n_docs = fail_interrupted_documents()
    if n_docs:
        logger.warning("Marked %d interrupted document-processing job(s) as failed/ready on startup.", n_docs)
    yield
    shutdown_clone_worker()


app = FastAPI(title="EchoLearn API", lifespan=lifespan)

# FRONTEND_URL may be a single origin or a comma-separated list (e.g. a production domain
# plus a Vercel preview-deployment URL) so both can call this API during a deploy.
_allowed_origins = [origin.strip() for origin in settings.FRONTEND_URL.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    error_label = HTTPStatus(exc.status_code).phrase
    return JSONResponse(status_code=exc.status_code, content={"error": error_label, "detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0] if exc.errors() else None
    message = first_error["msg"] if first_error else "Invalid request."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation Error", "detail": message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error", "detail": "Something went wrong. Please try again."},
    )


app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(folders_router)
app.include_router(chats_router)
app.include_router(quizzes_router)
app.include_router(review_router)
app.include_router(review_cards_router)
app.include_router(study_plans_router)
app.include_router(past_papers_router)
app.include_router(practice_papers_router)
app.include_router(voice_router)
app.include_router(voice_clone_router)
app.include_router(workspaces_router)
app.include_router(analytics_router)
app.include_router(users_router)
app.include_router(admin_auth_router)
app.include_router(admin_users_router)
app.include_router(admin_system_router)
app.include_router(admin_moderation_router)
app.include_router(admin_config_router)
app.include_router(admin_plans_router)


@app.get("/health")
def health():
    return {"status": "ok"}
