import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Verified Carbon Credit Marketplace"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days for easy demo testing
    
    # Database
    DATABASE_URL: str = f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'carbon_marketplace.db')}"
    
    # Uploads
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    
    # Sequestration factors (tCO2e / tree / year default prototype assumptions)
    DEFAULT_SEQUESTRATION_RATE_PER_TREE: float = 0.05
    BASE_CREDIT_PRICE_INR: float = 1500.0  # ₹1500 / tCO2e

    # Satellite & Remote Sensing Configuration
    SENTINEL_STAC_URL: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    COPERNICUS_CLIENT_ID: str = os.getenv("COPERNICUS_CLIENT_ID", "")
    COPERNICUS_CLIENT_SECRET: str = os.getenv("COPERNICUS_CLIENT_SECRET", "")
    PLANETARY_COMPUTER_API_KEY: str = os.getenv("PLANETARY_COMPUTER_API_KEY", "")
    ENABLE_REAL_SATELLITE_QUERIES: bool = True  # Attempts real STAC/satellite query; cleanly falls back if unconfigured/offline

    # Machine Learning / Vision Configuration
    ML_MODEL_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "weights", "plantation_classifier_v1.pt"
    )

    class Config:
        case_sensitive = True

settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
