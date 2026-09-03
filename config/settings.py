import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Resolve project root (parent of config/)
PROJECT_ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    """Load all configuration from .env file and return as dict."""
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)

    config = {
        # Database
        "pg_host": os.getenv("PGHOST", "localhost"),
        "pg_port": int(os.getenv("PGPORT", "5432")),
        "pg_database": os.getenv("PGDATABASE", "argo_data"),
        "pg_user": os.getenv("PGUSER", "yashovardhan"),
        "pg_password": os.getenv("PGPASSWORD", ""),
        # API keys
        "groq_api_key": os.getenv("GROQ_API_KEY", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        # LLM provider
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        # Paths
        "chroma_db_path": os.getenv("CHROMA_DB_PATH", "./data/chroma_db"),
        "argo_download_path": os.getenv("ARGO_DOWNLOAD_PATH", "./data/downloads"),
        "project_root": str(PROJECT_ROOT),
        # App config
        "max_upload_size_mb": 200,
        "default_map_zoom": 4,
        "default_map_center_lat": 20.0,
        "default_map_center_lon": 75.0,
        "default_profile_limit": 100,
        "max_profiles_viz": 1000,
        "max_profiles_chat_context": 10,
        "session_secret": os.getenv("SESSION_SECRET", "floatchat_ocean_2026"),
    }

    # Resolve relative paths to absolute using project root
    for key in ("chroma_db_path", "argo_download_path"):
        p = Path(config[key])
        if not p.is_absolute():
            config[key] = str(PROJECT_ROOT / p)

    _create_data_directories(config)
    validate_config(config)
    return config


def _create_data_directories(config: dict) -> None:
    """Create required data directories if they don't exist."""
    dirs = [
        PROJECT_ROOT / "data" / "temp",
        PROJECT_ROOT / "data" / "processed",
        PROJECT_ROOT / "data" / "downloads",
        Path(config["chroma_db_path"]),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory exists: %s", d)


def get_db_connection_string(config: dict) -> str:
    """Build PostgreSQL connection string, omitting password if empty."""
    host = config["pg_host"]
    port = config["pg_port"]
    db = config["pg_database"]
    user = config["pg_user"]
    password = config.get("pg_password", "")

    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return f"postgresql://{user}@{host}:{port}/{db}"


def validate_config(config: dict) -> bool:
    """Validate required config fields and warn about missing API keys."""
    required = ["pg_host", "pg_port", "pg_database", "pg_user"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        logger.error("Missing required config fields: %s", missing)
        return False

    if not config.get("groq_api_key") or config["groq_api_key"] == "your_groq_api_key_here":
        logger.warning("GROQ_API_KEY not set — AI chat will be limited")

    if not config.get("openai_api_key") or config["openai_api_key"] == "your_openai_api_key_here":
        logger.warning("OPENAI_API_KEY not set — OpenAI fallback unavailable")

    if config["llm_provider"] not in ("groq", "openai"):
        logger.warning(
            "LLM_PROVIDER '%s' unknown, defaulting to groq", config["llm_provider"]
        )
        config["llm_provider"] = "groq"

    logger.info(
        "Config loaded: db=%s@%s:%s/%s, llm=%s",
        config["pg_user"],
        config["pg_host"],
        config["pg_port"],
        config["pg_database"],
        config["llm_provider"],
    )
    return True
