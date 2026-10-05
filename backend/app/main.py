from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.api.v1.router import router
from app.api.v1.reports import router as reports_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.data_transfer import router as data_router
from app.core.config import settings
from app.db.session import engine
from sqlalchemy import text
from fastapi import HTTPException

app=FastAPI(title="OpenInvoice API",version="0.1.0",description="Self-hosted invoice management API")
app.add_middleware(SessionMiddleware,secret_key=settings.secret_key,same_site="lax",https_only=settings.session_cookie_secure,max_age=60*60*24*14)
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_url],allow_credentials=True,allow_methods=["*"] ,allow_headers=["*"])
app.include_router(router,prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(data_router, prefix="/api/v1")
@app.get("/health")
async def health(): return {"status":"ok"}

@app.get("/health/ready")
async def readiness():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database is unavailable") from None
    return {"status": "ready"}
