"""
Hospital Resource Utilization & Patient Outcomes API
Backend: FastAPI for ETL & API. BI: Apache Superset (connect to same DB).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analytics, etl, alerts, exports, reports

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="ETL, analytics API, exports (CSV/Excel/PDF), and monthly reports for the Hospital Dashboard.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics.router)
app.include_router(etl.router)
app.include_router(alerts.router)
app.include_router(exports.router)
app.include_router(reports.router)


@app.get("/")
def root():
    return {
        "service": "Hospital Resource Utilization & Patient Outcomes API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
