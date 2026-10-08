from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_schema_migrations():
    """Ensures newly added columns are present in SQLite without requiring manual migrations."""
    if "sqlite" in settings.DATABASE_URL:
        import sqlite3
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(verifications)")
                cols = [r[1] for r in cur.fetchall()]
                new_cols = [
                    ("is_real_satellite", "BOOLEAN DEFAULT 0"),
                    ("satellite_source", "VARCHAR"),
                    ("acquisition_date", "VARCHAR"),
                    ("mean_ndvi", "FLOAT"),
                    ("min_ndvi", "FLOAT"),
                    ("max_ndvi", "FLOAT"),
                    ("vegetation_coverage_pct", "FLOAT"),
                    ("ai_model_name", "VARCHAR DEFAULT 'MobileNetV3-Plantation-v1'"),
                    ("ai_model_version", "VARCHAR DEFAULT '1.0.0'"),
                    ("ai_predicted_class", "VARCHAR"),
                    ("ai_confidence_pct", "FLOAT"),
                    ("image_phash", "VARCHAR"),
                    ("risk_score", "FLOAT DEFAULT 0.0"),
                    ("risk_level", "VARCHAR DEFAULT 'LOW'"),
                    ("risk_factors", "JSON"),
                    ("risk_explanation", "TEXT")
                ]
                for col_name, col_type in new_cols:
                    if col_name not in cols:
                        cur.execute(f"ALTER TABLE verifications ADD COLUMN {col_name} {col_type}")
                conn.commit()
                conn.close()
            except Exception:
                pass

import os
ensure_schema_migrations()
