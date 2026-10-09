"""Load backend/.env regardless of the current working directory."""

from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_ROOT / ".env"


def load_backend_env() -> Path:
    """Load ``backend/.env`` if it exists; otherwise fall back to CWD search."""
    if ENV_FILE.is_file():
        load_dotenv(ENV_FILE, override=False)
    else:
        load_dotenv(override=False)
    return ENV_FILE
