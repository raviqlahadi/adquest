"""QuestStore — the storage contract for adquest v2.

Contract rules every backend MUST honor:

1. **Copy-on-read.** All getters return copies. Mutating a returned dict
   has NO effect on stored state — mutations go through update_*/add_*.
   (This is what keeps FileStore and PostgresStore interchangeable;
   direct-reference mutation would silently work on file and no-op on SQL.)
2. **Commit-boundary persistence.** Mutations are buffered; nothing is
   durable until ``commit()``. Commands call ``commit()`` exactly where
   v1 called ``save_state()``. A command that errors before commit
   leaves stored state untouched.
3. **Dict boundary.** Entities cross the interface as plain dicts with
   the v1 field names (``desc``, ``xp``, ``status``, ``type``, ``focus``,
   ``tags``, ``priority``, ``parent``, ``children``, ``chain``,
   ``created``, ``completed``, ``drop_reason``). The player document
   holds: ``level``, ``title``, ``xp``, ``xp_next``, ``hp``, ``mp``,
   ``streak``, ``last_quest_date``, ``buffs``, ``achievements``.
   Dataclass row-mappers arrive with the Postgres backend (Q197.2).
4. **History is a FileStore detail.** The 50-entry cap lives inside
   FileStore only. Networked backends keep full history (the v2 point).
"""
from abc import ABC, abstractmethod
from typing import Iterator


class QuestStore(ABC):
    # --- lifecycle -------------------------------------------------------

    @abstractmethod
    def commit(self) -> None:
        """Persist all buffered mutations. v1 save_state() equivalent."""

    @abstractmethod
    def close(self) -> None:
        """Release the store (locks, connections). Does NOT commit."""

    def __enter__(self) -> "QuestStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # --- raw blob (migration tooling / tests only, not for commands) -----

    @abstractmethod
    def load(self) -> dict:
        """Return the full state blob (copy). v1 load_state() equivalent."""

    # --- quests -----------------------------------------------------------

    @abstractmethod
    def get_quest(self, qid: str) -> dict | None:
        """Return a copy of the quest, or None if not in the active pool."""

    @abstractmethod
    def list_quests(self, status: str | None = None, tag: str | None = None) -> list[tuple[str, dict]]:
        """Return (qid, quest) copies in insertion order, filtered.

        status=None returns quests of every status.
        """

    @abstractmethod
    def add_quest(self, qid: str, quest: dict) -> None:
        """Insert a new quest (copy stored)."""

    @abstractmethod
    def update_quest(self, qid: str, fields: dict) -> None:
        """Merge fields into an existing quest."""

    # --- history (archived quests) -----------------------------------------

    @abstractmethod
    def move_to_history(self, qid: str) -> None:
        """Remove a quest from the active pool and archive it with its id."""

    @abstractmethod
    def restore_from_history(self, qid: str) -> dict | None:
        """Pop a quest from history back into the active pool (id stripped).

        Returns the restored quest dict, or None if not found in history.
        """

    @abstractmethod
    def get_history(self) -> list[tuple[str, dict]]:
        """Return (qid, entry) copies of archived quests."""

    # --- chains -------------------------------------------------------------

    @abstractmethod
    def get_chain(self, name: str) -> dict | None:
        """Return a copy of the chain {name, quests, current}, or None."""

    @abstractmethod
    def upsert_chain(self, name: str, chain: dict) -> None:
        """Insert or replace a chain."""

    @abstractmethod
    def delete_chain(self, name: str) -> None:
        """Remove a chain if present."""

    # --- player ---------------------------------------------------------------

    @abstractmethod
    def get_player(self) -> dict:
        """Return a copy of the player document."""

    @abstractmethod
    def update_player(self, fields: dict) -> None:
        """Merge fields into the player document."""

    # --- queries (achievement engine lands on these) --------------------------

    @abstractmethod
    def completed_between(self, start: str, end: str, tag: str | None = None) -> list[tuple[str, dict]]:
        """Quests with status=done completed on dates in [start, end] (ISO, inclusive).

        Scans both the active pool and history.
        """

    @abstractmethod
    def count_completed(self, tag: str | None = None) -> int:
        """Count all-time completions, optionally filtered by tag."""

    # --- convenience -----------------------------------------------------------

    def all_quest_ids(self) -> list[str]:
        """Every quest id ever allocated (active pool + history)."""
        ids = [qid for qid, _ in self.list_quests()]
        ids += [qid for qid, _ in self.get_history()]
        return ids
