"""State persistence — file-backed JSON (becomes FileStore internals in Q197.1)."""
import json
import sys

from .. import paths
from ..render import colored, vprint, C_RED, C_YELLOW

DEFAULT_STATE = {
    "level": 1,
    "title": "Apprentice of the Forge",
    "xp": 0,
    "xp_next": 100,
    "hp": 100,
    "mp": 100,
    "streak": 0,
    "last_quest_date": None,
    "quests": {},
    "chains": {},
    "history": [],
    "buffs": [],
    "achievements": [],
}


def ensure_dirs() -> None:
    """Create data and logs directories if they don't exist."""
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    """Load state from disk. Falls back to backup or defaults on corruption."""
    ensure_dirs()
    if paths.STATE_FILE.exists():
        vprint(f"Loading state from {paths.STATE_FILE}")
        try:
            return json.loads(paths.STATE_FILE.read_text())
        except json.JSONDecodeError as e:
            # Try backup before giving up
            backup = paths.STATE_FILE.with_suffix(".json.bak")
            if backup.exists():
                print(colored(f"⚠️  State corrupted ({e}). Restoring from backup.", C_YELLOW))
                try:
                    return json.loads(backup.read_text())
                except (json.JSONDecodeError, OSError):
                    pass
            print(colored("❌ State file corrupted and no valid backup. Starting fresh.", C_RED))
            return DEFAULT_STATE.copy()
        except OSError as e:
            print(colored(f"❌ Cannot read state file: {e}", C_RED))
            sys.exit(1)
    return DEFAULT_STATE.copy()


def save_state(state: dict) -> None:
    """Save state to disk with automatic backup. Exits on failure."""
    ensure_dirs()
    # Backup current state before overwriting
    if paths.STATE_FILE.exists():
        try:
            backup = paths.STATE_FILE.with_suffix(".json.bak")
            backup.write_text(paths.STATE_FILE.read_text())
            vprint(f"Backup saved to {backup}")
        except OSError:
            pass  # Non-fatal — proceed with save
    try:
        paths.STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
        vprint(f"State saved to {paths.STATE_FILE}")
    except OSError as e:
        print(colored(f"❌ Failed to save state: {e}", C_RED))
        sys.exit(1)
