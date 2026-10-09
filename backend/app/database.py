import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        # SQLite ignores FOREIGN KEY constraints unless this pragma is enabled per connection.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create missing tables, then add any model columns missing from older databases.

    This is a lightweight additive migration for the SQLite prototype database: it only
    ever ADDs nullable columns / indexes and never drops or rewrites existing data.
    """
    from . import models  # noqa: F401  (registers all models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _add_missing_indexes()
    _backfill_photo_records()


def _backfill_photo_records() -> None:
    """Older plantations stored one photo in plantations.image_url: give each a photo row (additive)."""
    from .services.photo_store import backfill_legacy_photos

    db = SessionLocal()
    try:
        created = backfill_legacy_photos(db)
        if created:
            logger.info("Created %d photo records for single-photo plantations", created)
    except Exception as exc:  # never block startup on this
        db.rollback()
        logger.warning("Photo backfill skipped: %s", exc)
    finally:
        db.close()


def _add_missing_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                default_sql = ""
                default = column.default.arg if column.default is not None and not callable(column.default.arg) else None
                if isinstance(default, bool):
                    default_sql = f" DEFAULT {1 if default else 0}"
                elif isinstance(default, (int, float)):
                    default_sql = f" DEFAULT {default}"
                elif isinstance(default, str):
                    escaped = default.replace("'", "''")
                    default_sql = f" DEFAULT '{escaped}'"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_sql}'))
                logger.info("Added missing column %s.%s", table.name, column.name)


def _add_missing_indexes() -> None:
    """One credit lot per plantation. Only created if existing data already satisfies it."""
    with engine.begin() as conn:
        dupes = conn.execute(
            text("SELECT plantation_id FROM credits GROUP BY plantation_id HAVING COUNT(*) > 1")
        ).fetchall()
        if dupes:
            logger.warning(
                "Not adding unique index on credits.plantation_id: %d plantations already have duplicate credits.",
                len(dupes),
            )
            return
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_credits_plantation_id ON credits (plantation_id)")
        )
