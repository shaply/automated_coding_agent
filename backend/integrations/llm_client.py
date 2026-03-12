"""
LiteLLM wrapper with:
- Per-provider daily token budget tracking (via usage_db)
- Proactive RPM throttling (minimum inter-request delay)
- Exponential backoff + jitter on 429s
- Provider fallback chain (Claude → Gemini → Groq)
- Respect for Retry-After headers
"""

import os
import time
import random
import logging
from typing import Any

import litellm
from litellm.exceptions import RateLimitError, ContextWindowExceededError

from .usage_db import UsageDB

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, providers_config: dict, fallback_order: list[str], usage_db: UsageDB):
        self.providers = providers_config  # keyed by provider name
        self.usage_db = usage_db
        self._last_request_ts: dict[str, float] = {}  # provider → unix timestamp

        # Build effective fallback order: skip providers with no API key configured.
        self.fallback_order: list[str] = []
        for provider in fallback_order:
            cfg = providers_config.get(provider, {})
            key_env = cfg.get("api_key_env")
            if key_env and not os.environ.get(key_env):
                logger.warning(
                    "Provider '%s' skipped — env var %s is not set. "
                    "Set it in .env to enable this provider.",
                    provider, key_env,
                )
                continue
            self.fallback_order.append(provider)

        if not self.fallback_order:
            raise RuntimeError(
                "No LLM providers are configured with API keys. "
                "Set at least one provider key in your .env file."
            )
        logger.info("Active LLM providers (in fallback order): %s", self.fallback_order)

    def _throttle(self, provider: str) -> None:
        """Enforce minimum inter-request delay to stay under RPM limits."""
        cfg = self.providers[provider]
        min_interval = cfg.get("min_request_interval", 0.0)
        last_ts = self._last_request_ts.get(provider, 0.0)
        elapsed = time.monotonic() - last_ts
        if elapsed < min_interval:
            wait = min_interval - elapsed
            logger.debug("Throttling %s: waiting %.1fs", provider, wait)
            time.sleep(wait)

    def _call_with_backoff(self, provider: str, fn, max_retries: int) -> Any:
        """Call fn(), retrying on 429 with exponential backoff + jitter."""
        for attempt in range(max_retries):
            self._throttle(provider)
            try:
                self._last_request_ts[provider] = time.monotonic()
                result = fn()
                return result
            except RateLimitError as exc:
                if attempt == max_retries - 1:
                    raise
                # Respect Retry-After header if present
                retry_after = getattr(exc, "retry_after", None)
                if retry_after:
                    wait = float(retry_after)
                else:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                wait = max(wait, 2.0)  # minimum 2s
                logger.warning(
                    "Rate limited by %s. Waiting %.1fs before retry %d/%d...",
                    provider, wait, attempt + 1, max_retries - 1,
                )
                time.sleep(wait)

    def complete(self, messages: list[dict], **kwargs) -> str:
        """
        Call the LLM with the given messages, routing through the fallback chain.
        Returns the response content string.
        Raises RuntimeError if all providers are exhausted.
        """
        max_retries = kwargs.pop("max_retries", 5)

        for provider in self.fallback_order:
            cfg = self.providers[provider]
            model = cfg["model"]
            daily_budget = cfg.get("daily_token_budget", float("inf"))

            # Check daily budget
            used_today = self.usage_db.get_usage(provider)
            if used_today >= daily_budget:
                logger.info(
                    "Provider %s daily budget exhausted (%d/%d). Trying next.",
                    provider, used_today, daily_budget,
                )
                continue

            def _call():
                return litellm.completion(model=model, messages=messages, **kwargs)

            try:
                response = self._call_with_backoff(provider, _call, max_retries)
            except RateLimitError:
                logger.warning("Provider %s exhausted retries on rate limit. Trying next.", provider)
                continue
            except litellm.exceptions.BadRequestError as exc:
                # Treat billing/credit errors as budget exhaustion → fallback, not crash
                msg = str(exc).lower()
                if "credit" in msg or "billing" in msg or "balance" in msg or "quota" in msg:
                    logger.warning(
                        "Provider %s billing error (credit/quota issue) — skipping to next provider. Error: %s",
                        provider, exc,
                    )
                    continue
                raise  # other bad request errors (e.g. invalid prompt) should propagate
            except ContextWindowExceededError as exc:
                logger.error(
                    "Context window exceeded for %s (model=%s): %s — not retrying.",
                    provider, model, exc,
                )
                raise

            # Track token usage
            tokens_used = response.usage.total_tokens if response.usage else 0
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            self.usage_db.add_usage(provider, tokens_used)
            new_total = used_today + tokens_used
            budget_pct = (new_total / daily_budget * 100) if daily_budget != float("inf") else 0
            logger.info(
                "LLM call: provider=%s model=%s  prompt=%d completion=%d total=%d  "
                "daily=%d/%d (%.1f%%)",
                provider, model, prompt_tokens, completion_tokens, tokens_used,
                new_total, daily_budget, budget_pct,
            )
            if budget_pct >= 80:
                logger.warning(
                    "Token budget WARNING: %s at %.1f%% daily budget (%d/%d tokens). "
                    "Consider conserving usage.",
                    provider, budget_pct, new_total, daily_budget,
                )

            content = response.choices[0].message.content
            return content

        raise RuntimeError(
            "All providers exhausted — daily budgets depleted or rate limits hit. "
            "Try again tomorrow or add more providers to the fallback chain."
        )
