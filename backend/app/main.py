import os
import sys

# Ensure both project root and backend folder are in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_current_dir)
_root_dir = os.path.dirname(_backend_dir)
for _p in (_backend_dir, _root_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.app.core.config import settings
from backend.app.core.logging import setup_logging, logger
from backend.app.core.database import init_db
from backend.app.seed_data import seed_database
from backend.app.api.v1 import enquiries, documents, orders, analytics, audit

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database and models...")
    init_db()
    try:
        seed_database()
    except Exception as e:
        logger.warning(f"Seed database warning: {e}")
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutdown.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered Customer Support Operations Platform with RAG, Tool-Calling, and Human Review Workflow.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 API routes
app.include_router(enquiries.router, prefix=settings.API_V1_STR)
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(orders.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health"])
def health_check():
    """System health and operational mode check."""
    active_prov = settings.active_provider
    if active_prov == "gemini":
        engine_label = f"Google Gemini ({settings.LLM_MODEL})"
    elif active_prov == "openai":
        engine_label = f"OpenAI ({settings.LLM_MODEL})"
    else:
        engine_label = "Deterministic Demo Engine (No external API key set)"

    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "demo_mode": settings.is_demo_mode,
        "provider": active_prov,
        "llm_engine": engine_label,
        "docs_url": "/docs"
    }
