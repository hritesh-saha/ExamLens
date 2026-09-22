"""
check_env.py — Environment Verification Script
===============================================
Run this after completing Step 1 to confirm that:
  1. Python version is correct
  2. All required packages are importable
  3. Tesseract is installed and reachable
  4. The .env file is loaded correctly

Usage:
    python backend/app/check_env.py

Expected output: All checks pass (green OK messages).
"""

import sys
import os

# ── ANSI colours for clear pass/fail messages ──────────────────────────────
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓  {msg}{RESET}")
def fail(msg): print(f"  {RED}✗  {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}!  {msg}{RESET}")

# ── 1. Python version ──────────────────────────────────────────────────────
print("\n[1] Python Version")
version = sys.version_info
if version.major == 3 and version.minor >= 11:
    ok(f"Python {version.major}.{version.minor}.{version.micro}")
else:
    fail(
        f"Python {version.major}.{version.minor} found. "
        "Need Python 3.11 or higher."
    )

# ── 2. Package imports ──────────────────────────────────────────────────────
print("\n[2] Required Packages")

packages = [
    ("pdfplumber",    "pdfplumber"),
    ("PyMuPDF",       "fitz"),
    ("pytesseract",   "pytesseract"),
    ("Pillow",        "PIL"),
    ("FastAPI",       "fastapi"),
    ("Pydantic",      "pydantic"),
    ("python-dotenv", "dotenv"),
    ("pytest",        "pytest"),
    ("httpx",         "httpx"),
]

all_ok = True
for display_name, import_name in packages:
    try:
        __import__(import_name)
        ok(display_name)
    except ImportError:
        fail(f"{display_name}  ← not installed. Run: pip install -r backend/requirements.txt")
        all_ok = False

# ── 3. .env file ────────────────────────────────────────────────────────────
print("\n[3] Environment File (.env)")

# Walk up from this file's location to find the backend/.env
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)   # backend/
env_path = os.path.join(backend_dir, ".env")

if os.path.exists(env_path):
    ok(f".env found at: {env_path}")
else:
    fail(
        f".env NOT found. "
        "Copy backend/.env.example to backend/.env and fill in your values."
    )

# Load .env and read TESSERACT_PATH
try:
    from dotenv import load_dotenv
    load_dotenv(env_path)
    tess_path = os.getenv("TESSERACT_PATH", "")
    db_url    = os.getenv("DATABASE_URL", "")
    env_name  = os.getenv("ENV", "development")

    if tess_path:
        ok(f"TESSERACT_PATH = {tess_path}")
    else:
        warn("TESSERACT_PATH not set in .env")

    if db_url:
        ok(f"DATABASE_URL   = {db_url}")
    else:
        warn("DATABASE_URL not set in .env")

    ok(f"ENV            = {env_name}")
except Exception as e:
    fail(f"Could not load .env: {e}")

# ── 4. Tesseract binary ─────────────────────────────────────────────────────
print("\n[4] Tesseract OCR Binary")
try:
    import pytesseract

    # Use path from .env if available
    tess_path = os.getenv("TESSERACT_PATH", "")
    if tess_path and os.path.exists(tess_path):
        pytesseract.pytesseract.tesseract_cmd = tess_path
        ok(f"Tesseract binary found: {tess_path}")
    else:
        warn(
            "TESSERACT_PATH not found in .env or file doesn't exist. "
            "Trying system PATH..."
        )

    # Actually call tesseract to get version
    version_str = pytesseract.get_tesseract_version()
    ok(f"Tesseract version: {version_str}")

except Exception as e:
    fail(
        f"Tesseract not working: {e}\n"
        "     Download from: https://github.com/UB-Mannheim/tesseract/wiki\n"
        "     Then set TESSERACT_PATH in backend/.env"
    )

# ── 5. Folder structure ─────────────────────────────────────────────────────
print("\n[5] Folder Structure")

# Compute project root (two levels up from app/)
project_root = os.path.dirname(backend_dir)

required_dirs = [
    os.path.join(backend_dir, "app", "exam_parser"),
    os.path.join(backend_dir, "app", "syllabus"),
    os.path.join(backend_dir, "app", "database"),
    os.path.join(backend_dir, "app", "api"),
    os.path.join(backend_dir, "tests"),
    os.path.join(backend_dir, "data", "papers"),
    os.path.join(backend_dir, "data", "syllabus"),
    os.path.join(backend_dir, "output"),
]

for d in required_dirs:
    rel = os.path.relpath(d, project_root)
    if os.path.isdir(d):
        ok(rel)
    else:
        fail(f"{rel}  ← directory missing")

# ── Summary ─────────────────────────────────────────────────────────────────
print("\n" + "─" * 50)
if all_ok:
    print(f"{GREEN}All checks passed. Step 1 is complete!{RESET}")
else:
    print(f"{RED}Some checks failed. Fix the issues above and re-run.{RESET}")
print("─" * 50 + "\n")
