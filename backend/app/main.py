from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.api.v1.router import router
from app.core.config import settings

app=FastAPI(title="OpenInvoice API",version="0.1.0",description="Self-hosted invoice management API")
app.add_middleware(SessionMiddleware,secret_key=settings.secret_key,same_site="lax",https_only=settings.session_cookie_secure,max_age=60*60*24*14)
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_url],allow_credentials=True,allow_methods=["*"] ,allow_headers=["*"])
app.include_router(router,prefix="/api/v1")
@app.get("/health")
async def health(): return {"status":"ok"}

