"""Utility functions for calling Google Generative Language models."""

from __future__ import annotations

import os
from typing import Optional

import requests
import streamlit as st

# Default model/version – adjust if you want to target a different endpoint.
GENAI_MODEL = "models/text-bison-001"
GENAI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/{GENAI_MODEL}:generateText"


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
    secrets = getattr(st, "secrets", {})
    if secrets and "GOOGLE_API_KEY" in secrets:
        return secrets["GOOGLE_API_KEY"]

    # Local environment
    env_key = os.environ.get("GOOGLE_API_KEY")
    if env_key:
        return env_key

    raise RuntimeError(
        "Google API key not found. Set GOOGLE_API_KEY in Streamlit secrets or the environment."
    )


def call_google_text(prompt: str, *, temperature: float = 0.3, max_tokens: int = 512) -> str:
    """
    Call the Google Generative Language API with the supplied prompt.

    Parameters
    ----------
    prompt : str
        Prompt text to send to the model.
    temperature : float, optional
        Sampling temperature.
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
        "prompt": {"text": prompt},
        "temperature": temperature,
        "maxOutputTokens": max_tokens,
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

    return candidates[0].get("output", "").strip()
