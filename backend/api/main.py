"""
TariffIQ V2 FastAPI application.

Run locally (manual):
  cd vanguard-ai
  pip install -r backend/requirements.txt
  uvicorn backend.api.main:app --reload --port 8000
"""

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import admin_router, health_router, query_router
from backend.config.settings import get_settings

load_dotenv()

settings = get_settings()

app = FastAPI(
    title="TariffIQ",
    description="US import duty classification and estimation API (V2)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(query_router)
app.include_router(admin_router)
