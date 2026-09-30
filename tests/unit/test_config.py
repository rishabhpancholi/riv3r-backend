from app.core.config import Settings


def test_cors_allowed_origins_are_loaded_from_environment(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        '["http://localhost:3000", "https://app.example.com"]',
    )

    settings = Settings(
        _env_file=None,
        database_url="https://example.supabase.co",
        database_key="database-key",
        cache_password="cache-password",
        jwt_secret_key="jwt-secret",
    )

    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "https://app.example.com",
    ]
