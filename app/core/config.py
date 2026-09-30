from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RIV3R"
    app_version: str = "0.0.1"
    app_mode: str = "DEVELOPMENT"
    cors_allowed_origins: list[str] = Field(default_factory=list)

    database_url: str 
    database_key: str

    cache_host: str = "localhost"
    cache_port: int = 6379
    cache_username: str = "default"
    cache_password: str 
    cache_ttl: int = 300

    jwt_secret_key: str  
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    login_max_requests: int = 5
    login_window_seconds: int = 60

    @property
    def is_production(self) -> bool:
        return self.app_mode.upper() == "PRODUCTION"


@lru_cache
def load_settings() -> Settings:
    return Settings()
