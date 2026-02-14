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

    # Simulation mode (no real APIs required)
    SIMULATION_MODE: bool = True
    SIMULATION_DELAY_MS: int = 800

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
