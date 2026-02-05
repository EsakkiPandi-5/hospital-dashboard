"""
ETL API: run schema, seed data, refresh (re-run seed).
"""
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.config import settings

router = APIRouter(prefix="/api/etl", tags=["etl"])


@router.post("/run-schema")
def run_schema():
    """Apply database schema (schema.sql). Uses psql if available, else runs SQL via engine."""
    schema_path = Path(__file__).resolve().parent.parent.parent / "database" / "schema.sql"
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="database/schema.sql not found")
    db_url = settings.database_url
    if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        result = subprocess.run(
            ["psql", db_url, "-f", str(schema_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and "already exists" not in (result.stderr or ""):
            raise HTTPException(status_code=500, detail=result.stderr or result.stdout)
        return {"status": "ok", "message": "Schema applied via psql."}
    with open(schema_path) as f:
        sql = f.read()
    try:
        with engine.connect() as conn:
            for stmt in sql.split(";"):
                s = stmt.strip()
                if s and not s.startswith("--"):
                    try:
                        conn.execute(text(s + ";"))
                    except Exception as ex:
                        if "already exists" not in str(ex).lower():
                            raise
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "message": "Schema applied."}


@router.post("/seed")
def seed():
    """Run seed_data.py to populate sample data."""
    seed_path = Path(__file__).resolve().parent.parent.parent / "database" / "seed_data.py"
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail="database/seed_data.py not found")
    result = subprocess.run(
        [sys.executable, str(seed_path)],
        env={**__import__("os").environ, "DATABASE_URL": settings.database_url},
        capture_output=True,
        text=True,
        cwd=str(seed_path.parent),
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr or result.stdout)
    return {"status": "ok", "message": "Seed completed.", "stdout": result.stdout}
