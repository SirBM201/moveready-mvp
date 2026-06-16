from __future__ import annotations

import os


def env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name, "1" if default else "0").lower()
    return value in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name, str(default)) or str(default))
    except Exception:
        return default


ENV_MODE = env("ENV_MODE", env("ENV", "development"))
FLASK_ENV = env("FLASK_ENV", "development")
PORT = env_int("PORT", 8000)
SECRET_KEY = env("SECRET_KEY")

API_PREFIX = env("API_PREFIX", "/api")
if API_PREFIX and not API_PREFIX.startswith("/"):
    API_PREFIX = "/" + API_PREFIX
API_PREFIX = API_PREFIX.rstrip("/") or "/api"

CORS_ORIGINS = env("CORS_ORIGINS", "http://localhost:3000")

SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY") or env("SUPABASE_SERVICE_KEY")

OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-4o-mini")

ADMIN_API_KEY = (
    env("MOVEREADY_ADMIN_API_KEY")
    or env("MOVE_READY_ADMIN_API_KEY")
    or env("ADMIN_API_KEY")
)

SESSION_COOKIE_NAME = env("SESSION_COOKIE_NAME", "moveready_session")
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", FLASK_ENV != "development")
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", "Lax")
PERMANENT_SESSION_LIFETIME = env_int("PERMANENT_SESSION_LIFETIME", 2592000)
