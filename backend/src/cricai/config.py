from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRICAI_", env_file=ROOT / ".env", extra="ignore")
    database_url: str = ""
    dev_token: str = ""
    allow_test_data: bool = False
