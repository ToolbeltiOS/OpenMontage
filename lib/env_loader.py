"""Environment variable loader for OpenMontage.

Loads .env file and provides typed access to environment configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_env(project_root: Optional[Path] = None) -> None:
    """Load .env from the project root, then from the workspace above it.

    THERE ARE TWO, AND ONLY ONE WAS BEING READ. The project keeps its own
    `.env`, and `~/Developer/wak3up-docs/.env` is the workspace file shared
    with the other pipelines in that tree. A key added to the workspace file
    -- which is the natural place for one shared with the Shorts run --
    was invisible here, and the symptom was a correct-looking
    "PIXAZO_API_KEY is not set" from a script that had just been told the
    key existed.

    The project's own file is loaded FIRST so it still wins: `load_dotenv`
    does not overwrite a variable that is already set, so the workspace file
    only fills in what the project has not defined.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    for env_path in (project_root / ".env", project_root.parent / ".env"):
        if env_path.exists():
            load_dotenv(env_path)


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get an environment variable with optional default."""
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    """Get a required environment variable. Raises if missing."""
    value = os.environ.get(key)
    if value is None:
        raise EnvironmentError(f"Required environment variable {key!r} is not set")
    return value
