"""Environment config loader — explicit env file per settings module."""

import os
from pathlib import Path

from decouple import Config, RepositoryEmpty, RepositoryEnv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

_ENV_FILES: dict[str, Path] = {
    "core_settings.settings.dev": BASE_DIR / ".env-dev",
    "core_settings.settings.prod": BASE_DIR / ".env",
}

_settings_module = os.environ.get(
    "DJANGO_SETTINGS_MODULE", "core_settings.settings.dev"
)
_env_file = _ENV_FILES.get(_settings_module, BASE_DIR / ".env")

if _env_file.is_file():
    config = Config(RepositoryEnv(str(_env_file)))
else:
    # CI / Docker: all values come from real environment variables
    config = Config(RepositoryEmpty())
