import logging
import os
import secrets
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Placeholder only. If SECRET_KEY is not configured, a random key is generated on first start
# and saved to backend/.env (see _ensure_secret_key below).
_DEV_SECRET_KEY = "dev-only-insecure-secret-key-change-me"

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Runtime configuration.

    Every field can be overridden with an environment variable of the same name or
    a line in ``backend/.env`` (see ``backend/.env.example``).
    """

    model_config = SettingsConfigDict(
        env_file=os.path.join(BACKEND_DIR, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "AI-Verified Carbon Credit Marketplace"
    API_V1_STR: str = "/api"

    # --- Auth ---
    SECRET_KEY: str = _DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # --- CORS ---
    # Comma-separated list of allowed browser origins, or "*" for any origin.
    # The API uses bearer tokens (not cookies), so credentials are not required.
    CORS_ORIGINS: str = "*"

    # --- Database ---
    DATABASE_URL: str = f"sqlite:///{os.path.join(BACKEND_DIR, 'carbon_marketplace.db')}"

    # --- Uploads ---
    UPLOAD_DIR: str = os.path.join(BACKEND_DIR, "uploads")
    MAX_UPLOAD_BYTES: int = 15 * 1024 * 1024  # 15 MB per image
    MAX_PHOTOS_PER_PLANTATION: int = 10       # active ground photos per plantation
    # Photos are served only through signed links issued to authorised users.
    PHOTO_URL_TTL_S: int = 3600
    # Multi-photo CV: below this classifier confidence (%) a photo counts as low-confidence.
    CV_LOW_CONFIDENCE_PCT: float = 60.0
    # pHash Hamming distance at or below which two photos are treated as near-duplicates.
    PHOTO_NEAR_DUPLICATE_DISTANCE: int = 6

    # --- Carbon estimation (transparent prototype assumptions) ---
    DEFAULT_SEQUESTRATION_RATE_PER_TREE: float = 0.05  # tCO2e / tree / year
    BASE_CREDIT_PRICE_INR: float = 1500.0  # INR / tCO2e

    # --- Satellite / remote sensing ---
    SENTINEL_STAC_URL: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    PLANETARY_COMPUTER_SAS_URL: str = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
    PLANETARY_COMPUTER_API_KEY: str = ""
    # When False the backend never contacts the satellite service; NDVI must then be
    # supplied as reported evidence (value + source + acquisition date) or stays PENDING.
    ENABLE_REAL_SATELLITE_QUERIES: bool = True
    SATELLITE_REQUEST_TIMEOUT_S: float = 20.0
    # Scene search window and filters (documented in backend/README.md)
    SATELLITE_LOOKBACK_DAYS: int = 120          # search scenes acquired in the last N days
    SATELLITE_MAX_SCENE_CLOUD_PCT: float = 20.0  # scene-level eo:cloud_cover upper limit
    SATELLITE_MAX_SCENES_TRIED: int = 3          # least-cloudy scenes tried before giving up
    # Bounded retries for transient failures (timeouts, connection errors, HTTP 429/5xx)
    SATELLITE_MAX_ATTEMPTS: int = 3
    SATELLITE_RETRY_BACKOFF_S: float = 1.0       # 1 s, 2 s, 4 s ... (Retry-After honoured, capped)

    # --- Machine learning (ground photo classifier) ---
    ML_MODEL_PATH: str = os.path.join(BACKEND_DIR, "ml", "weights", "plantation_classifier_v2.pt")
    ML_METADATA_PATH: str = os.path.join(BACKEND_DIR, "ml", "weights", "model_metadata.json")

    # --- Blockchain (local Ganache) ---
    ETHEREUM_RPC_URL: str = "http://127.0.0.1:8545"
    # Set to False to skip on-chain registration entirely (credits are then marked NOT_RECORDED).
    ENABLE_BLOCKCHAIN: bool = True

    @property
    def cors_origin_list(self) -> List[str]:
        raw = (self.CORS_ORIGINS or "").strip()
        if raw == "*" or not raw:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]



_PLACEHOLDER_SECRETS = {_DEV_SECRET_KEY, "change-me", "changeme", ""}


def _ensure_secret_key(cfg: "Settings") -> None:
    """Replace a missing/placeholder SECRET_KEY with a random one stored in backend/.env.

    Runs once per install: the generated key is written to backend/.env (git-ignored), so
    tokens stay valid across restarts and every developer machine gets its own key.
    """
    if cfg.SECRET_KEY not in _PLACEHOLDER_SECRETS:
        return
    env_path = os.path.join(BACKEND_DIR, ".env")
    new_key = secrets.token_hex(32)
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = [ln for ln in f.read().splitlines() if not ln.strip().startswith("SECRET_KEY=")]
        lines.append(f"SECRET_KEY={new_key}")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        cfg.SECRET_KEY = new_key
        logger.warning("Generated a new SECRET_KEY and saved it to %s", env_path)
    except OSError as exc:
        cfg.SECRET_KEY = new_key  # still never run with a known key; tokens reset on restart
        logger.warning("Could not write %s (%s); using a random SECRET_KEY for this run only.", env_path, exc)


settings = Settings()
_ensure_secret_key(settings)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
