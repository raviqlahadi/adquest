"""CLI configuration: level table + rest presets."""
import json
import sys

from .. import paths
from ..render import colored, C_RED, C_YELLOW

DEFAULT_CONFIG = {
    "levels": [
        {"level": 1, "title": "Apprentice of the Forge", "xp_next": 100},
        {"level": 2, "title": "Journeyman Codewright", "xp_next": 150},
        {"level": 3, "title": "Adept of the Iron Stack", "xp_next": 200},
        {"level": 4, "title": "Wardkeeper", "xp_next": 300},
        {"level": 5, "title": "Runesmith", "xp_next": 400},
        {"level": 6, "title": "Archon of Systems", "xp_next": 500},
        {"level": 7, "title": "Voidwalker", "xp_next": 650},
        {"level": 8, "title": "Mythral Architect", "xp_next": 800},
        {"level": 9, "title": "Elder of the Obsidian Guild", "xp_next": 1000},
        {"level": 10, "title": "Ascendant", "xp_next": None},
    ],
    "rest_presets": {
        "lunch": {"hp": 20, "mp": 30},
        "coffee": {"hp": 0, "mp": 10},
        "nap": {"hp": 10, "mp": 20},
        "sleep": {"hp": "=100", "mp": "=100"},
        "gaming": {"hp": 5, "mp": 15},
        "shower": {"hp": 15, "mp": 10},
        "dj": {"hp": 0, "mp": 20},
        "sprint": {"hp": 15, "mp": 25},
    },
}


def load_config() -> dict:
    """Load config from disk, falling back to defaults on error."""
    if paths.CONFIG_FILE.exists():
        try:
            return json.loads(paths.CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(colored(f"⚠️  Config corrupted ({e}). Using defaults.", C_YELLOW))
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


def save_config(config: dict) -> None:
    """Write config to disk. Exits on failure."""
    try:
        paths.CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")
    except OSError as e:
        print(colored(f"❌ Failed to save config: {e}", C_RED))
        sys.exit(1)
