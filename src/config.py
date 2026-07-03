"""
Central configuration: API keys, workspace path, and model discovery.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root, if present

# --- API keys -----------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

# --- Workspace ------------------------------------------------------------
# All file/code tools are sandboxed to this directory. The agent can never
# read or write outside of it.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# --- Fallback model lists ---------------------------------------------
# Used if we can't reach the provider's "list models" endpoint (e.g. no
# key set yet, or offline). Kept short and current as of mid-2026.
FALLBACK_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
    "deepseek-r1-distill-llama-70b",
]

FALLBACK_GOOGLE_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


def list_groq_models() -> list[str]:
    """Fetch the live list of Groq models, falling back to a static list."""
    if not GROQ_API_KEY:
        return FALLBACK_GROQ_MODELS
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)
        models = client.models.list()
        ids = sorted(m.id for m in models.data if getattr(m, "active", True))
        # Keep only chat-capable-looking models (drop whisper/tts, etc.)
        blocked = ("whisper", "tts", "guard", "prompt-guard")
        ids = [m for m in ids if not any(b in m.lower() for b in blocked)]
        return ids or FALLBACK_GROQ_MODELS
    except Exception:
        return FALLBACK_GROQ_MODELS


def list_google_models() -> list[str]:
    """Fetch the live list of Gemini models, falling back to a static list."""
    if not GOOGLE_API_KEY:
        return FALLBACK_GOOGLE_MODELS
    try:
        from google import genai

        client = genai.Client(api_key=GOOGLE_API_KEY)
        names = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" in actions:
                names.append(m.name.replace("models/", ""))
        names = sorted(set(names))
        return names or FALLBACK_GOOGLE_MODELS
    except Exception:
        return FALLBACK_GOOGLE_MODELS