import os
import logging
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Development-only signing key. Override with the SECRET_KEY environment variable
# (or backend/.env) for any shared or deployed environment.
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
    SATELLITE_REQUEST_TIMEOUT_S: float = 10.0

    # --- Machine learning (ground photo classifier) ---
    ML_MODEL_PATH: str = os.path.join(BACKEND_DIR, "ml", "weights", "plantation_classifier_v1.pt")
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

    @property
    def using_dev_secret(self) -> bool:
        return self.SECRET_KEY == _DEV_SECRET_KEY


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

if settings.using_dev_secret:
    logger.warning(
        "SECRET_KEY is using the built-in development value. "
        "Set SECRET_KEY in backend/.env before sharing or deploying this backend."
    )
