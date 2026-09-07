"""Filesystem path constants for adquest.

IMPORTANT: all modules must access these via attribute lookup
(``paths.STATE_FILE``), never ``from .paths import STATE_FILE`` —
tests rebind attributes on this module to redirect state to temp dirs.
"""
from pathlib import Path

DATA_DIR = Path.home() / ".adquest"
STATE_FILE = DATA_DIR / "state.json"
CONFIG_FILE = DATA_DIR / "config.json"
LOGS_DIR = DATA_DIR / "logs"
