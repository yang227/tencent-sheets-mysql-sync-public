"""
Test fixtures — isolate tests from real environment variables.
"""
import os
import pytest


@pytest.fixture(autouse=True)
def _clear_tencent_token_env(monkeypatch):
    """
    Remove TENCENT_DOCS_ACCESS_TOKEN from the environment for the duration of each test.

    This ensures TencentAPI tests that pass access_token=... or expect OAuth flows
    are not inadvertently affected by a real token set in the shell/.env.
    """
    monkeypatch.delenv("TENCENT_DOCS_ACCESS_TOKEN", raising=False)
