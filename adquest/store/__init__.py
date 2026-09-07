"""Storage backends for adquest.

``open_store()`` is the single seam commands use to obtain a store.
Q197.4 wires config/env/CLI overrides into this factory; for now it
always returns the FileStore.
"""
from .base import QuestStore
from .file import FileStore, DEFAULT_STATE, HISTORY_CAP

__all__ = ["QuestStore", "FileStore", "DEFAULT_STATE", "HISTORY_CAP", "open_store"]


def open_store() -> QuestStore:
    """Return the configured store backend. (Backend selection lands in Q197.4.)"""
    return FileStore()
