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
from app.quizzes.routes import router as quizzes_router
from app.users.routes import router as users_router
from app.voice.routes import router as voice_router
from app.workspaces.routes import router as workspaces_router
from app.voice.tts import load_voice_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.VOICE_BACKEND == "local":
        load_voice_model()  # Loaded once here, not per-request — model load is the slow part.
    yield


app = FastAPI(title="EchoLearn API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
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
app.include_router(voice_router)
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
