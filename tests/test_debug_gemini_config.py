import config


def test_debug_gemini_is_never_enabled_in_production(monkeypatch):
    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.setenv("ENABLE_DEBUG_GEMINI", "true")
    assert config.is_debug_gemini_enabled() is False
