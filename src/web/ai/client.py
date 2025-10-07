"""Utility functions for calling Google Generative Language (Gemini) models."""

from __future__ import annotations

import os
from typing import Optional

import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

# Default model/version – adjust via GOOGLE_GENAI_MODEL env if needed.
# Updated to use Gemini 2.5 Flash (the latest available model as of 2025)
_model_name = os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

# The endpoint should be structured as /v1beta/models/{model}:{method}
# The "models/" prefix is part of the path, not the model name itself.
if _model_name.startswith("models/"):
    _model_name = _model_name.split("/")[-1]

GENAI_MODEL = _model_name
GENAI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GENAI_MODEL}:generateContent"


def get_google_api_key() -> str:
    """
    Fetch the Google API key from Streamlit secrets or the environment.

    Returns
    -------
    str
        API key string.

    Raises
    ------
    RuntimeError
        If the key is missing.
    """
    # Streamlit Cloud / secrets.toml
    secrets_obj: Optional[object] = None
    try:
        secrets_obj = getattr(st, "secrets", None)
    except Exception:
        secrets_obj = None

    if secrets_obj is not None:
        try:
            return secrets_obj["GOOGLE_API_KEY"]  # type: ignore[index]
        except (KeyError, TypeError, AttributeError, StreamlitSecretNotFoundError):
            pass
        except Exception:
            pass

    # Local environment
    env_key = os.environ.get("GOOGLE_API_KEY")
    if env_key:
        return env_key

    raise RuntimeError(
        "Google Gemini API key not found. Set GOOGLE_API_KEY in Streamlit secrets or the environment."
    )


def call_google_text(
    prompt: str, *, temperature: float = 0.3, max_tokens: int = 512
) -> str:
    """
    Call the Google Gemini API with the supplied prompt.

    Parameters
    ----------
    prompt : str
        Prompt text to send to the model.
    temperature : float, optional
        Sampling temperature (0.0–1.0).
    max_tokens : int, optional
        Maximum number of tokens in the response.

    Returns
    -------
    str
        Model response text.

    Raises
    ------
    requests.HTTPError
        If the HTTP request fails.
    RuntimeError
        If no candidates are returned.
    """
    api_key = get_google_api_key()

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    response = requests.post(
        f"{GENAI_ENDPOINT}?key={api_key}",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()

    # Check for API errors first
    if "error" in data:
        error_msg = data["error"].get("message", "Unknown API error")
        raise RuntimeError(f"Gemini API error: {error_msg}")

    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("No response candidates returned by the model.")

    first = candidates[0]
    content = first.get("content") or {}

    # Handle different response structures
    # Sometimes the text is in parts, sometimes directly in content
    parts = content.get("parts") or []

    # Collect all text parts
    text_parts = []

    # First check if there are parts with text
    for part in parts:
        if isinstance(part, dict) and "text" in part and part["text"]:
            text_parts.append(part["text"])

    # If no text found in parts, check if text is directly in content
    if not text_parts and "text" in content:
        text_parts.append(content["text"])

    # Also check if the candidate has text directly
    if not text_parts and "text" in first:
        text_parts.append(first["text"])

    if not text_parts:
        # Check if response hit token limit with empty content
        finish_reason = first.get("finishReason", "")
        if finish_reason == "MAX_TOKENS":
            raise RuntimeError(
                f"Model response was truncated (MAX_TOKENS reached). "
                f"Try reducing max_tokens or simplifying the prompt."
            )

        # Debug: show what we got instead
        import json
        debug_info = json.dumps(data, indent=2)[:500]
        raise RuntimeError(f"Model response did not include text content. Response structure: {debug_info}")

    # Join all text parts
    full_text = " ".join(text_parts).strip()

    if not full_text:
        raise RuntimeError("Model response text was empty after processing.")

    return full_text
