"""PostgresStore — PostgreSQL-backed QuestStore (Q197.2).

Design notes
------------
**JSONB document rows, not typed quest columns.** Quest dicts are
schema-elastic in v1 (optional ``drop_reason``, forward-compatible
fields) and the store contract is dict-boundary (rule 3). Each row
therefore keeps a canonical ``data`` jsonb column that round-trips
dicts exactly; queried attributes stay SQL-addressable
(``data->>'status'``, ``(data->'tags') ? tag``) behind expression
indexes. At personal-tasklist scale, column projection buys nothing.

**Identity columns for ordering.** v1 dicts preserve insertion order
(``list_quests`` contract). The ``ord``/``hord`` identity columns
reproduce it; gaps from rolled-back transactions are harmless — only
monotonicity matters. Re-adding an existing qid keeps its original
position (``ON CONFLICT DO UPDATE`` leaves ``ord`` untouched), matching
dict-assignment semantics.

**History is uncapped** (contract rule 4). ``hord`` is archive order,
mirroring FileStore's append-only list; ``restore_from_history`` pops
the OLDEST matching entry — exactly FileStore's first-match scan.

**Session advisory lock = the networked flock.** Transactions alone
don't stop two concurrent read-modify-write cycles from losing updates.
``pg_try_advisory_lock`` with FileStore's bounded-retry policy is held
construction→close(), so only one store — on any machine — mutates a
database at a time.

**Transaction discipline** (contract rule 2). autocommit stays OFF:
bootstrap (schema + default seed) commits immediately, then command
mutations accumulate and become durable only at ``commit()``.
``close()`` rolls back — a command that dies before commit leaves
stored state untouched, for free.

**DSN resolution:** explicit constructor arg → ``ADQUEST_DSN`` env →
QuestError. (Config-file / CLI selection lands in Q197.4.)

Caveat: jsonb does not preserve object key order, so dicts read back
may differ in key order from v1 files. No contract behavior depends
on key order.
"""
from __future__ import annotations

import os
import time
from copy import deepcopy

import psycopg
from psycopg.types.json import Jsonb

from ..errors import QuestError
from ..render import colored, C_RED
from .base import QuestStore
from .file import DEFAULT_STATE, _PLAYER_KEYS, _default_for

__all__ = ["PostgresStore"]

# Mirrors FileStore's flock policy — bounded retries absorb fast
# contention between short commands.
LOCK_RETRIES = 5
LOCK_RETRY_DELAY = 0.02  # seconds

# Session advisory-lock key: b"adquest" read as a bigint. One lock per
# database — every store instance, on any machine, competes for it.
LOCK_KEY = 0x61647175657374

# Bootstrap is idempotent and runs under the advisory lock, so racing
# constructors serialize safely.
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS quests (
        qid  text PRIMARY KEY,
        ord  bigint GENERATED ALWAYS AS IDENTITY,
        data jsonb NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history (
        hord bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        qid  text NOT NULL,
        data jsonb NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS history_qid_idx ON history (qid)",
    """
    CREATE TABLE IF NOT EXISTS chains (
        name text PRIMARY KEY,
        ord  bigint GENERATED ALWAYS AS IDENTITY,
        data jsonb NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS player (
        id   integer PRIMARY KEY CHECK (id = 1),
        data jsonb NOT NULL
    )
    """,
    # Expression indexes over the documents — keep SQL-side filtering
    # viable as the quest pool grows.
    "CREATE INDEX IF NOT EXISTS quests_status_idx ON quests ((data->>'status'))",
    "CREATE INDEX IF NOT EXISTS quests_tags_gin_idx ON quests USING gin ((data->'tags'))",
)

_DSN_ENV = "ADQUEST_DSN"


def _short(err: Exception) -> str:
    """First line of a psycopg error — the rest is context noise for a CLI."""
    return str(err).strip().splitlines()[0]


class PostgresStore(QuestStore):
    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get(_DSN_ENV)
        if not self._dsn:
            raise QuestError(colored(
                f"⚠️  No PostgreSQL DSN configured. Use --dsn, set {_DSN_ENV}, "
                f"or add postgres_dsn to config.json.", C_RED
            ))
        try:
            self._conn = psycopg.connect(self._dsn)
        except psycopg.Error as e:
            raise QuestError(colored(f"⚠️  Cannot reach PostgreSQL: {_short(e)}", C_RED)) from e
        try:
            self._acquire_lock()
            self._bootstrap()
            # Schema + seed are durable now; command mutations buffer from here.
            self._conn.commit()
        except QuestError:
            self._conn.rollback()
            self._conn.close()
            raise
        except psycopg.Error as e:
            self._conn.rollback()
            self._conn.close()
            raise QuestError(colored(f"⚠️  PostgreSQL bootstrap failed: {_short(e)}", C_RED)) from e

    # --- internals -----------------------------------------------------------

    def _acquire_lock(self) -> None:
        """Session advisory lock — the networked equivalent of FileStore's flock.

        Session-scoped, so it survives the bootstrap commit and is released
        by close(). Held construction→close(), exactly like the flock.
        """
        for attempt in range(LOCK_RETRIES):
            held = self._conn.execute(
                "SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,)
            ).fetchone()[0]
            if held:
                return
            if attempt < LOCK_RETRIES - 1:
                time.sleep(LOCK_RETRY_DELAY)
        raise QuestError(colored(
            "⚠️  Another adquest process holds the state lock. Try again in a moment.", C_RED
        ))

    def _bootstrap(self) -> None:
        for stmt in _SCHEMA:
            self._conn.execute(stmt)
        seed = {k: DEFAULT_STATE[k] for k in _PLAYER_KEYS}
        self._conn.execute(
            "INSERT INTO player (id, data) VALUES (1, %s) ON CONFLICT (id) DO NOTHING",
            (Jsonb(seed),),
        )

    # --- lifecycle -------------------------------------------------------------

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        conn = getattr(self, "_conn", None)
        if conn is None or conn.closed:
            return
        try:
            # Uncommitted mutations die here — close() never commits (contract).
            conn.rollback()
        finally:
            # Releases the session advisory lock too.
            conn.close()

    # --- raw blob ----------------------------------------------------------------

    def load(self) -> dict:
        """Reassemble the full v1 blob, in DEFAULT_STATE key order."""
        player = self.get_player()
        quests = dict(self.list_quests())
        chains = dict(self._chains_ordered())
        history = [{"id": qid, **quest} for qid, quest in self.get_history()]
        blob: dict = {}
        for key in DEFAULT_STATE:
            if key == "quests":
                blob[key] = quests
            elif key == "chains":
                blob[key] = chains
            elif key == "history":
                blob[key] = history
            else:
                blob[key] = player[key]
        return blob

    def _chains_ordered(self) -> list[tuple[str, dict]]:
        rows = self._conn.execute(
            "SELECT name, data FROM chains ORDER BY ord"
        ).fetchall()
        return [(name, deepcopy(data)) for name, data in rows]

    # --- quests -------------------------------------------------------------------

    def get_quest(self, qid: str) -> dict | None:
        row = self._conn.execute(
            "SELECT data FROM quests WHERE qid = %s", (qid,)
        ).fetchone()
        return deepcopy(row[0]) if row is not None else None

    def list_quests(self, status: str | None = None, tag: str | None = None) -> list[tuple[str, dict]]:
        rows = self._conn.execute(
            """
            SELECT qid, data FROM quests
            WHERE (%s::text IS NULL OR data->>'status' = %s)
              AND (%s::text IS NULL OR (data->'tags') ? %s::text)
            ORDER BY ord
            """,
            (status, status, tag, tag),
        ).fetchall()
        return [(qid, deepcopy(data)) for qid, data in rows]

    def add_quest(self, qid: str, quest: dict) -> None:
        # ON CONFLICT keeps the original ord — dict-assignment semantics.
        self._conn.execute(
            "INSERT INTO quests (qid, data) VALUES (%s, %s) "
            "ON CONFLICT (qid) DO UPDATE SET data = EXCLUDED.data",
            (qid, Jsonb(quest)),
        )

    def update_quest(self, qid: str, fields: dict) -> None:
        cur = self._conn.execute(
            "UPDATE quests SET data = data || %s WHERE qid = %s",
            (Jsonb(fields), qid),
        )
        if cur.rowcount == 0:
            raise QuestError(f"Internal: update_quest on missing quest {qid}")

    # --- history ----------------------------------------------------------------------

    def move_to_history(self, qid: str) -> None:
        row = self._conn.execute(
            "DELETE FROM quests WHERE qid = %s RETURNING data", (qid,)
        ).fetchone()
        if row is not None:
            # No cap — networked backends keep full history (contract rule 4).
            self._conn.execute(
                "INSERT INTO history (qid, data) VALUES (%s, %s)", (qid, Jsonb(row[0]))
            )

    def restore_from_history(self, qid: str) -> dict | None:
        row = self._conn.execute(
            """
            DELETE FROM history
            WHERE hord = (SELECT hord FROM history WHERE qid = %s ORDER BY hord LIMIT 1)
            RETURNING data
            """,
            (qid,),
        ).fetchone()
        if row is None:
            return None
        data = deepcopy(row[0])
        # Fresh identity value → restored quest lands at the end of the pool,
        # matching FileStore dict insertion.
        self._conn.execute(
            "INSERT INTO quests (qid, data) VALUES (%s, %s)", (qid, Jsonb(data))
        )
        return deepcopy(data)

    def get_history(self) -> list[tuple[str, dict]]:
        rows = self._conn.execute("SELECT qid, data FROM history ORDER BY hord").fetchall()
        return [(qid, deepcopy(data)) for qid, data in rows]

    # --- chains ------------------------------------------------------------------------

    def get_chain(self, name: str) -> dict | None:
        row = self._conn.execute(
            "SELECT data FROM chains WHERE name = %s", (name,)
        ).fetchone()
        return deepcopy(row[0]) if row is not None else None

    def upsert_chain(self, name: str, chain: dict) -> None:
        # ON CONFLICT keeps the original ord — dict-assignment semantics.
        self._conn.execute(
            "INSERT INTO chains (name, data) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET data = EXCLUDED.data",
            (name, Jsonb(chain)),
        )

    def delete_chain(self, name: str) -> None:
        self._conn.execute("DELETE FROM chains WHERE name = %s", (name,))

    # --- player ------------------------------------------------------------------------

    def get_player(self) -> dict:
        row = self._conn.execute("SELECT data FROM player WHERE id = 1").fetchone()
        data = row[0] if row is not None else {}
        return {k: deepcopy(data.get(k, _default_for(k))) for k in _PLAYER_KEYS}

    def update_player(self, fields: dict) -> None:
        known = {k: v for k, v in fields.items() if k in _PLAYER_KEYS}
        if not known:
            return
        self._conn.execute(
            "UPDATE player SET data = data || %s WHERE id = 1", (Jsonb(known),)
        )

    # --- queries ------------------------------------------------------------------------

    # The two filters below deliberately mirror FileStore's Python-side
    # logic (string-sliced dates, tag membership) so both backends stay
    # behaviorally identical. If they ever diverge, hoist into base.

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
