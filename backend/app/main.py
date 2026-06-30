from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import auth, inspection, projects, reports, rules
from app.core.config import settings
from app.core.cors import configure_cors
from app.core.database import create_schema
from app.core.exceptions import BusinessError, business_error_handler
from app.seed import seed_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    seed_database()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
configure_cors(app)
app.add_exception_handler(BusinessError, business_error_handler)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(rules.router)
app.include_router(inspection.router)
app.include_router(reports.router)
