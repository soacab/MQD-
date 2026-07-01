from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def configure_cors(app: FastAPI) -> None:
    allow_origins = settings.cors_origins
    if settings.is_production and "*" in allow_origins:
        raise RuntimeError("CHECKFLOW_CORS_ORIGINS must not include * in production when credentials are enabled.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
