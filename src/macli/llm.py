"""Lightweight OpenAI-compatible LLM client wrapper."""

from __future__ import annotations

from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

from macli.config import Settings


class LLMError(Exception):
    """Raised when an LLM API call fails."""


class LLMClient:
    """Universal wrapper around the OpenAI Python SDK.

    Supports any OpenAI-compatible provider (Groq, OpenRouter, Gemini, Ollama, OpenAI)
    via `base_url`, `api_key`, and `model` from Settings.
    """

    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        self.settings = settings
        self._client = client or OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout,
        )

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion request and return the assistant's text response.

        Args:
            system_prompt: System instructions defining the agent role.
            user_prompt: The task/input message for the agent.
            temperature: Optional override for sampling temperature.
            json_mode: If True, request a JSON object response when supported.

        Returns:
            The response text from the model.

        Raises:
            LLMError: If the API call fails due to auth, rate limits, or network errors.
        """
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.temperature if temperature is None else temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._client.chat.completions.create(**kwargs)
        except AuthenticationError as exc:
            raise LLMError(
                "Authentication failed (401). Please verify your `LLM_API_KEY` and "
                "`LLM_BASE_URL` in `.env`."
            ) from exc
        except RateLimitError as exc:
            raise LLMError(
                "API rate limit exceeded (429). Please wait a moment and try again, "
                "or switch to another model/provider in `.env`."
            ) from exc
        except APITimeoutError as exc:
            raise LLMError(
                f"Request timed out after {self.settings.timeout:.0f}s. "
                "Check your network connection or increase `LLM_TIMEOUT` in `.env`."
            ) from exc
        except APIConnectionError as exc:
            raise LLMError(
                f"Could not connect to `{self.settings.base_url}`. "
                "Verify your internet connection (or ensure Ollama is running if local)."
            ) from exc
        except APIStatusError as exc:
            detail = getattr(exc, "message", str(exc))
            raise LLMError(
                f"LLM API returned HTTP {exc.status_code}: {detail}"
            ) from exc
        except OpenAIError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

        if not response.choices:
            raise LLMError("LLM returned an empty choices list.")

        content = response.choices[0].message.content
        if content is None:
            raise LLMError("LLM returned an empty message content.")

        return content.strip()
