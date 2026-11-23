"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def _ignore_personal_env_settings(monkeypatch):
    """Tests must not depend on a teammate's .env. python-dotenv never overrides a
    variable that is already set, so an empty value here wins over the .env line."""
    monkeypatch.setenv("ACME_STUB_AGENTS", "")
