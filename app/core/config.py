from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str
    app_version: str
    app_mode: str

    database_url: str
    database_key: str

    cache_host: str
    cache_port: int
    cache_username: str
    cache_password: str
    cache_ttl: int

    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int
    jwt_refresh_token_expire_days: int

    login_max_requests: int
    login_window_seconds: int

    @property
    def is_production(self) -> bool:
        return self.app_mode.upper() == "PRODUCTION"


@lru_cache
def load_settings() -> Settings:
    return Settings()
