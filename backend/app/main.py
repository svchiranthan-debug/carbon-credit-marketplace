import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import (
    auth_router,
    users_router,
    plantations_router,
    verification_router,
    carbon_router,
    marketplace_router,
    transactions_router,
    admin_router,
)

# Create tables and add any columns missing from older SQLite databases (additive only)
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Decentralized multi-modal verification platform for agroforestry carbon credits.",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # bearer tokens, no cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(plantations_router, prefix=settings.API_V1_STR)
app.include_router(verification_router, prefix=settings.API_V1_STR)
app.include_router(carbon_router, prefix=settings.API_V1_STR)
app.include_router(marketplace_router, prefix=settings.API_V1_STR)
app.include_router(transactions_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "online",
        "documentation": "/docs",
        "verification_formula": "0.40 x NDVI + 0.35 x CV + 0.25 x SOC",
        "version": "1.0.0"
    }

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "carbon-credit-backend"}
