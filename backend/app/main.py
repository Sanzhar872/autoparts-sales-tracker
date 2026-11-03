from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import auth
from app.db import get_session
from app.routers import cars, entries, reports, returns, sales

app = FastAPI(title="Трекер продаж авторазбора", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health(session: Session = Depends(get_session)):
    """Пинг для внешнего cron: держит проект Supabase активным."""
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "error"}, status_code=503)
    return {"status": "ok"}


api = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])
for module in (entries, sales, returns, cars, reports):
    api.include_router(module.router)

app.include_router(auth.router)
app.include_router(api)
