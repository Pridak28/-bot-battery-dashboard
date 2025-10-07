"""Utility functions for calling Google Generative Language (Gemini) models."""

from __future__ import annotations

import os
from typing import Optional

import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

# Default model/version – adjust via GOOGLE_GENAI_MODEL env if needed.
_model_name = os.environ.get("GOOGLE_GENAI_MODEL", "gemini-1.5-flash")

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
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("No response candidates returned by the model.")

    first = candidates[0]
    content = first.get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        raise RuntimeError("Model response did not include text content.")

    text = parts[0].get("text", "")
    if not text:
        raise RuntimeError("Model response text was empty.")
    return text.strip()
