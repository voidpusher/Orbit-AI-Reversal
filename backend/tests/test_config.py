from app.core.config import Settings


def test_vercel_urls_default_to_production_host(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "orbit.example.vercel.app")
    monkeypatch.delenv("ORBIT_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("ORBIT_FRONTEND_BASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.public_base_url == "https://orbit.example.vercel.app"
    assert settings.frontend_base_url == "https://orbit.example.vercel.app"
