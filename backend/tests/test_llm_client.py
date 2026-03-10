"""Tests for integrations/llm_client.py"""

import os
import pytest
from unittest.mock import MagicMock, patch, call
from integrations.llm_client import LLMClient
from integrations.usage_db import UsageDB


def _make_response(content="ok", total_tokens=100):
    resp = MagicMock()
    resp.choices[0].message.content = content
    resp.usage.total_tokens = total_tokens
    return resp


def _make_llm(db_path, fallback_order=None, extra_env=None):
    """Helper to build an LLMClient with mocked env vars."""
    env = {"ANTHROPIC_API_KEY": "test-key"}
    if extra_env:
        env.update(extra_env)

    providers = {
        "claude": {
            "model": "claude-3-5-sonnet-20241022",
            "api_key_env": "ANTHROPIC_API_KEY",
            "daily_token_budget": 25000,
            "min_request_interval": 0,
        },
        "gemini": {
            "model": "gemini/gemini-1.5-flash",
            "api_key_env": "GEMINI_API_KEY",
            "daily_token_budget": 1500,
            "min_request_interval": 0,
        },
    }
    db = UsageDB(db_path)
    order = fallback_order or ["claude", "gemini"]

    with patch.dict(os.environ, env, clear=False):
        client = LLMClient(providers_config=providers, fallback_order=order, usage_db=db)
    return client, db


def test_active_providers_only_includes_keyed_providers(db_path):
    """Providers without API keys are excluded from fallback_order."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "GEMINI_API_KEY": ""}, clear=False):
        client, _ = _make_llm(db_path)
        assert "claude" in client.fallback_order
        assert "gemini" not in client.fallback_order


def test_raises_if_no_providers_keyed(db_path):
    providers = {
        "claude": {"model": "x", "api_key_env": "ANTHROPIC_API_KEY", "daily_token_budget": 100, "min_request_interval": 0}
    }
    db = UsageDB(db_path)
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
        with pytest.raises(RuntimeError, match="No LLM providers"):
            LLMClient(providers_config=providers, fallback_order=["claude"], usage_db=db)


def test_complete_calls_litellm_and_returns_content(db_path):
    client, db = _make_llm(db_path)
    fake_response = _make_response("Hello!")

    with patch("litellm.completion", return_value=fake_response) as mock_complete:
        result = client.complete([{"role": "user", "content": "hi"}])

    assert result == "Hello!"
    mock_complete.assert_called_once()


def test_complete_tracks_token_usage(db_path):
    client, db = _make_llm(db_path)

    with patch("litellm.completion", return_value=_make_response(total_tokens=250)):
        client.complete([{"role": "user", "content": "hi"}])

    assert db.get_usage("claude") == 250


def test_complete_skips_exhausted_provider(db_path):
    """When Claude's daily budget is used up, fall through to gemini."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "GEMINI_API_KEY": "k2"}, clear=False):
        providers = {
            "claude": {
                "model": "claude-model",
                "api_key_env": "ANTHROPIC_API_KEY",
                "daily_token_budget": 10,
                "min_request_interval": 0,
            },
            "gemini": {
                "model": "gemini-model",
                "api_key_env": "GEMINI_API_KEY",
                "daily_token_budget": 99999,
                "min_request_interval": 0,
            },
        }
        db = UsageDB(db_path)
        # Burn Claude's budget
        db.add_usage("claude", 10)

        client = LLMClient(providers_config=providers, fallback_order=["claude", "gemini"], usage_db=db)
        fake = _make_response("from gemini")

        with patch("litellm.completion", return_value=fake) as mock:
            result = client.complete([{"role": "user", "content": "hi"}])

        assert result == "from gemini"
        # Should have called gemini model, not claude
        call_kwargs = mock.call_args
        assert "gemini-model" in str(call_kwargs)


def test_complete_raises_when_all_exhausted(db_path):
    client, db = _make_llm(db_path)
    # Exhaust claude's budget
    db.add_usage("claude", 99999)

    with pytest.raises(RuntimeError, match="All providers exhausted"):
        client.complete([{"role": "user", "content": "hi"}])


def test_rate_limit_retries_then_raises(db_path):
    from litellm.exceptions import RateLimitError
    client, db = _make_llm(db_path)

    with patch("litellm.completion", side_effect=RateLimitError("rate limited", llm_provider="claude", model="claude")):
        with patch("time.sleep"):  # don't actually sleep
            with pytest.raises(RuntimeError, match="All providers exhausted"):
                client.complete([{"role": "user", "content": "hi"}], max_retries=2)
