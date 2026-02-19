from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.resume import router as resume_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="ATS Optimizer API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(resume_router)
    return app


app = create_app()
