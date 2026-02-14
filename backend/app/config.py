from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Azure Configuration
    AZURE_SUBSCRIPTION_ID: str = "00000000-0000-0000-0000-000000000000"
    AZURE_RESOURCE_GROUP: str = "codeops-sentinel-rg"
    AZURE_OPENAI_ENDPOINT: str = "https://your-openai.openai.azure.com/"
    AZURE_OPENAI_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"
    AZURE_MONITOR_WORKSPACE: str = ""

    # GitHub Configuration
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = "your-org/your-repo"
    GITHUB_BASE_BRANCH: str = "main"

    # Application Configuration
    APP_ENV: str = "development"
    APP_NAME: str = "CodeOps Sentinel"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Simulation mode — set to False when real Azure credentials are present.
    # FoundryService also auto-detects: if AZURE_OPENAI_KEY is set and
    # SIMULATION_MODE is False, real GPT-4o calls are made.
    SIMULATION_MODE: bool = True
    SIMULATION_DELAY_MS: int = 800

    # Confidence threshold for automated remediation (0–100 scale).
    # >= threshold  → auto-fix and deploy
    # <  threshold  → escalate to human review (skip deploy phase)
    CONFIDENCE_THRESHOLD: int = 70

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
