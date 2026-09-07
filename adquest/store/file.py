"""FileStore — file-backed QuestStore, v1 JSON semantics preserved.

The on-disk format (~/.adquest/state.json) is byte-compatible with v1:
one JSON blob with player fields at the top level, ``quests`` dict,
``chains`` dict, ``history`` list, ``buffs``, ``achievements``.

Concurrency: an exclusive non-blocking flock is held on
``~/.adquest/state.lock`` from construction to ``close()`` — two
concurrent invocations can no longer read-modify-write race. The lock
file is opened with O_CREAT (never truncated, never deleted) and a
short bounded retry absorbs fast contention between short commands.
"""
import errno
import fcntl
import json
import os
import sys
import time
from copy import deepcopy

from .. import paths
from ..errors import QuestError
from ..render import colored, vprint, C_RED, C_YELLOW
from .base import QuestStore

HISTORY_CAP = 50  # v1 parity — networked backends drop this cap

LOCK_RETRIES = 5
LOCK_RETRY_DELAY = 0.02  # seconds — a whole adquest command runs in <100ms

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

# Keys of the blob owned by the player document (everything else is
# quests/chains/history — collections the store manages separately).
_PLAYER_KEYS = (
    "level", "title", "xp", "xp_next", "hp", "mp",
    "streak", "last_quest_date", "buffs", "achievements",
)


class FileStore(QuestStore):
    def __init__(self) -> None:
        self._ensure_dirs()
        self._lock_file = self._acquire_lock()
        self._blob = self._read()

    # --- internals ---------------------------------------------------------

    @staticmethod
    def _ensure_dirs() -> None:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _acquire_lock():
        """Open the persistent lock file and take an exclusive flock.

        O_RDWR|O_CREAT (no truncation, never unlinked) keeps the inode
        stable; bounded retries absorb fast contention between short
        commands. Raises QuestError when genuinely held.
        """
        last_err = None
        for attempt in range(LOCK_RETRIES):
            fd = os.open(paths.DATA_DIR / "state.lock", os.O_RDWR | os.O_CREAT, 0o644)
            f = os.fdopen(fd, "r+")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return f
            except OSError as e:
                f.close()
                if e.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                last_err = e
                if attempt < LOCK_RETRIES - 1:
                    time.sleep(LOCK_RETRY_DELAY)
        raise QuestError(colored(
            "⚠️  Another adquest process holds the state lock. Try again in a moment.", C_RED
        ))

    @staticmethod
    def _read() -> dict:
        """Load state from disk. Falls back to backup or defaults on corruption."""
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
                return deepcopy(DEFAULT_STATE)
            except OSError as e:
                print(colored(f"❌ Cannot read state file: {e}", C_RED))
                sys.exit(1)
        return deepcopy(DEFAULT_STATE)

    def _append_history(self, qid: str, quest: dict) -> None:
        """Archive a quest with its id, capped at HISTORY_CAP (v1 parity)."""
        self._blob["history"].append({"id": qid, **deepcopy(quest)})
        self._blob["history"] = self._blob["history"][-HISTORY_CAP:]

    # --- lifecycle -----------------------------------------------------------

    def commit(self) -> None:
        """Save state to disk with automatic backup. Exits on failure."""
        if paths.STATE_FILE.exists():
            try:
                backup = paths.STATE_FILE.with_suffix(".json.bak")
                backup.write_text(paths.STATE_FILE.read_text())
                vprint(f"Backup saved to {backup}")
            except OSError:
                pass  # Non-fatal — proceed with save
        try:
            paths.STATE_FILE.write_text(
                json.dumps(self._blob, indent=2, ensure_ascii=False) + "\n"
            )
            vprint(f"State saved to {paths.STATE_FILE}")
        except OSError as e:
            print(colored(f"❌ Failed to save state: {e}", C_RED))
            sys.exit(1)

    def close(self) -> None:
        f = getattr(self, "_lock_file", None)
        if f is None or f.closed:
            return
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()
            self._lock_file = None

    # --- raw blob ---------------------------------------------------------------

    def load(self) -> dict:
        return deepcopy(self._blob)

    # --- quests ---------------------------------------------------------------

    def get_quest(self, qid: str) -> dict | None:
        quest = self._blob["quests"].get(qid)
        return deepcopy(quest) if quest is not None else None

    def list_quests(self, status: str | None = None, tag: str | None = None) -> list[tuple[str, dict]]:
        out = []
        for qid, quest in self._blob["quests"].items():
            if status is not None and quest["status"] != status:
                continue
            if tag is not None and tag not in quest.get("tags", []):
                continue
            out.append((qid, deepcopy(quest)))
        return out

    def add_quest(self, qid: str, quest: dict) -> None:
        self._blob["quests"][qid] = deepcopy(quest)

    def update_quest(self, qid: str, fields: dict) -> None:
        quest = self._blob["quests"].get(qid)
        if quest is None:
            raise QuestError(f"Internal: update_quest on missing quest {qid}")
        quest.update(deepcopy(fields))

    # --- history ----------------------------------------------------------------

    def move_to_history(self, qid: str) -> None:
        quest = self._blob["quests"].pop(qid, None)
        if quest is not None:
            self._append_history(qid, quest)

    def restore_from_history(self, qid: str) -> dict | None:
        for i, entry in enumerate(self._blob["history"]):
            if entry.get("id") == qid:
                restored = self._blob["history"].pop(i)
                restored.pop("id")
                self._blob["quests"][qid] = restored
                return deepcopy(restored)
        return None

    def get_history(self) -> list[tuple[str, dict]]:
        return [(e["id"], deepcopy({k: v for k, v in e.items() if k != "id"}))
                for e in self._blob["history"]]

    # --- chains -------------------------------------------------------------------

    def get_chain(self, name: str) -> dict | None:
        chain = self._blob["chains"].get(name)
        return deepcopy(chain) if chain is not None else None

    def upsert_chain(self, name: str, chain: dict) -> None:
        self._blob["chains"][name] = deepcopy(chain)

    def delete_chain(self, name: str) -> None:
        self._blob["chains"].pop(name, None)

    # --- player ---------------------------------------------------------------------

    def get_player(self) -> dict:
        return {k: deepcopy(self._blob.get(k, _default_for(k))) for k in _PLAYER_KEYS}

    def update_player(self, fields: dict) -> None:
        for k, v in fields.items():
            if k in _PLAYER_KEYS:
                self._blob[k] = deepcopy(v)

    # --- queries -----------------------------------------------------------------------

    def completed_between(self, start: str, end: str, tag: str | None = None) -> list[tuple[str, dict]]:
        out = []
        for qid, quest in self.list_quests(status="done"):
            completed = quest.get("completed") or ""
            if start <= completed[:10] <= end and (tag is None or tag in quest.get("tags", [])):
                out.append((qid, quest))
        for qid, entry in self.get_history():
            if entry.get("status") != "done":
                continue
            completed = entry.get("completed") or ""
            if start <= completed[:10] <= end and (tag is None or tag in entry.get("tags", [])):
                out.append((qid, entry))
        return out

    def count_completed(self, tag: str | None = None) -> int:
        done = self.list_quests(status="done")
        hist = [(qid, e) for qid, e in self.get_history() if e.get("status") == "done"]
        return sum(
            1
            for _, q in done + hist
            if tag is None or tag in q.get("tags", [])
        )


def _default_for(key: str):
    """Default for player keys missing from older state files."""
    defaults = {"buffs": [], "achievements": [], "last_quest_date": None}
    return defaults.get(key)
