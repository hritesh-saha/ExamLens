"""Locate and configure the Tesseract OCR executable for pytesseract."""

from __future__ import annotations

import os
from pathlib import Path

import pytesseract

from app.env_loader import load_backend_env

_COMMON_WINDOWS_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def configure_tesseract() -> str | None:
    """Point pytesseract at TESSERACT_PATH, a common install location, or PATH.

    Returns the resolved executable path when one was found on disk.
    """
    load_backend_env()
    candidates: list[str] = []
    env_path = os.getenv("TESSERACT_PATH", "").strip().strip('"')
    if env_path:
        candidates.append(env_path)
    candidates.extend(_COMMON_WINDOWS_PATHS)

    for path in candidates:
        if path and Path(path).is_file():
            pytesseract.pytesseract.tesseract_cmd = path
            return path
    return None


def is_tesseract_available() -> bool:
    configure_tesseract()
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def tesseract_version() -> str | None:
    configure_tesseract()
    try:
        return str(pytesseract.get_tesseract_version())
    except Exception:
        return None
