"""Config helper tests for blast-radius guardrails."""
import config


def test_int_env_invalid_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "not-a-number")
    assert config._int_env("MAX_UPLOAD_BYTES", 1234) == 1234


def test_int_env_zero_or_negative_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "0")
    assert config._int_env("MAX_UPLOAD_BYTES", 1234) == 1234


def test_looks_like_pdf_accepts_leading_whitespace_and_bom():
    payload = b" \r\n\xef\xbb\xbf%PDF-1.4"
    assert config.looks_like_pdf(payload) is True


def test_looks_like_pdf_rejects_non_pdf():
    assert config.looks_like_pdf(b"plain text") is False
