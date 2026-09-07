"""Contract suite — identical behavior required from every backend.

Each scenario runs real CLI command handlers against a backend and
asserts outcomes through the store API. Q197.2 adds the Postgres
backend to BACKENDS; any contract failure there means a parity break.
"""

import argparse
import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

import adquest
import adquest.paths as paths
import adquest.store as store_mod
from adquest.store import DEFAULT_STATE
from adquest.store.file import FileStore

try:
    import psycopg
    from adquest.store.postgres import PostgresStore
    _HAS_POSTGRES = True
except ImportError:  # psycopg is an optional extra — file backend runs without it
    _HAS_POSTGRES = False

# Local dev cluster (~/pgdata/adquest-dev, user-space PG on sdo) —
# override with ADQUEST_TEST_DSN elsewhere.
TEST_DSN = "host=/tmp port=5433 dbname=adquest_test"

BACKENDS = {
    "file": FileStore,
}
if _HAS_POSTGRES:
    BACKENDS["postgres"] = PostgresStore


@pytest.fixture(params=sorted(BACKENDS), ids=sorted(BACKENDS))
def backend(request, monkeypatch):
    """Redirect paths to a per-test temp dir and force the backend.

    Tempdirs live on ext4 (~/.cache) rather than /tmp — tmpfs inode
    reuse can carry orphaned flocks from system daemons into fresh
    lock files.
    """
    root = Path.home() / ".cache" / "adquest-tests"
    root.mkdir(parents=True, exist_ok=True)
    data_dir = Path(tempfile.mkdtemp(prefix=f"adquest-{request.param}-", dir=root)) / ".adquest"
    monkeypatch.setattr(paths, "DATA_DIR", data_dir)
    monkeypatch.setattr(paths, "STATE_FILE", data_dir / "state.json")
    monkeypatch.setattr(paths, "CONFIG_FILE", data_dir / "config.json")
    monkeypatch.setattr(paths, "LOGS_DIR", data_dir / "logs")
    # Force the backend under test through the factory seam
    monkeypatch.setattr(store_mod, "open_store", BACKENDS[request.param])
    if request.param == "postgres":
        dsn = os.environ.get("ADQUEST_TEST_DSN", TEST_DSN)
        # Safety rail (Q197.5 lesson): this fixture DROPS the schema. It
        # must never point at a database holding real data.
        m = re.search(r"dbname=([^ ]+)", dsn)
        dbname = m.group(1) if m else ""
        if not dbname.endswith("_test"):
            pytest.fail(f"parity suite refuses non-test database {dbname!r} — "
                        "dbname must end with '_test'")
        monkeypatch.setenv("ADQUEST_DSN", dsn)
        # PostgresStore bootstraps schema + default seed itself; the
        # fixture only guarantees a clean slate. DROP+CREATE also resets
        # identity sequences (a TRUNCATE would need RESTART IDENTITY).
        try:
            with psycopg.connect(dsn, autocommit=True) as conn:
                conn.execute("DROP SCHEMA public CASCADE")
                conn.execute("CREATE SCHEMA public")
        except psycopg.OperationalError as e:
            pytest.skip(f"Postgres dev cluster unreachable at {dsn}: {e}")
    else:
        # Seed a clean state file
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "state.json").write_text(json.dumps(DEFAULT_STATE, indent=2))
    return request.param


def run(cmd, **kwargs):
    handler = {
        "quest": adquest.cli.cmd_quest,
        "sub": adquest.cli.cmd_sub,
        "done": adquest.cli.cmd_done,
        "focus": adquest.cli.cmd_focus,
        "unfocus": adquest.cli.cmd_unfocus,
        "chain": adquest.cli.cmd_chain,
        "edit": adquest.cli.cmd_edit,
        "drop": adquest.cli.cmd_drop,
        "reopen": adquest.cli.cmd_reopen,
        "drain": adquest.cli.cmd_drain,
        "rest": adquest.cli.cmd_rest,
        "newday": adquest.cli.cmd_newday,
    }[cmd]
    handler(argparse.Namespace(**kwargs))


def blob():
    with store_mod.open_store() as store:
        return store.load()


def test_quest_lifecycle_scenario(backend):
    run("quest", desc="Parent quest", xp=20, type="main", tag="work", priority="high")
    run("sub", parent="Q1", desc="Child step", xp=5, tag=None)
    run("focus", quest_id="Q1")

    state = blob()
    assert state["quests"]["Q1"]["focus"] is True
    assert state["quests"]["Q1.1"]["parent"] == "Q1"
    assert state["quests"]["Q1"]["children"] == ["Q1.1"]

    run("done", quest_id="Q1.1")
    state = blob()
    assert state["quests"]["Q1.1"]["status"] == "done"
    # v1 semantics: child's XP + parent auto-complete bonus (parent's own
    # XP is NOT awarded on auto-complete)
    assert state["xp"] == 10
    assert state["quests"]["Q1"]["status"] == "done"

    # Completing the auto-completed parent again is rejected
    with pytest.raises(adquest.QuestError, match="already completed"):
        run("done", quest_id="Q1")

    # Reopen reverses the parent's own XP only (floors at 0)
    run("reopen", quest_id="Q1")
    state = blob()
    assert state["quests"]["Q1"]["status"] == "active"
    assert state["xp"] == 0  # 10 - 20 floored

    run("done", quest_id="Q1")
    state = blob()
    assert state["xp"] == 20  # parent's own XP; child already done, no double award


def test_chain_scenario(backend):
    run("quest", desc="First", xp=5, type="main", tag=None, priority="med")
    run("quest", desc="Second", xp=5, type="main", tag=None, priority="med")
    run("chain", name="order", quests=["Q1", "Q2"])

    state = blob()
    assert state["chains"]["order"]["current"] == 0
    assert state["quests"]["Q2"]["chain"] == "order"

    # Out-of-order completion is blocked
    with pytest.raises(adquest.QuestError, match="blocked"):
        run("done", quest_id="Q2")

    run("done", quest_id="Q1")
    state = blob()
    assert state["chains"]["order"]["current"] == 1

    run("done", quest_id="Q2")
    state = blob()
    assert state["chains"]["order"]["current"] == 2


def test_drop_scenario(backend):
    run("quest", desc="Doomed", xp=5, type="main", tag=None, priority="med")
    run("sub", parent="Q1", desc="Doomed child", xp=5, tag=None)
    run("drop", quest_id="Q1", reason="cold trail")

    state = blob()
    assert "Q1" not in state["quests"]
    assert "Q1.1" not in state["quests"]
    dropped = [h for h in state["history"] if h.get("drop_reason") == "cold trail"]
    assert {h["id"] for h in dropped} == {"Q1", "Q1.1"}


def test_energy_scenario(backend):
    run("drain", hp=30, mp=10, reason="deep debugging")
    state = blob()
    assert state["hp"] == 70 and state["mp"] == 90

    run("rest", activity="lunch")
    state = blob()
    assert state["hp"] == 90 and state["mp"] == 100

    run("newday")
    state = blob()
    assert state["hp"] == 100 and state["mp"] == 100


def test_query_scenario(backend):
    run("quest", desc="Tagged A", xp=5, type="main", tag="alpha", priority="med")
    run("quest", desc="Tagged B", xp=5, type="main", tag="beta", priority="med")
    run("done", quest_id="Q1")
    run("done", quest_id="Q2")

    today = blob()["quests"]["Q1"]["completed"][:10]
    # NOTE: never open a second store while one is held (the lock forbids
    # nesting by design) — blob() calls stay OUTSIDE the with-block below.
    with store_mod.open_store() as store:
        assert store.count_completed() == 2
        assert store.count_completed(tag="alpha") == 1
        assert {qid for qid, _ in store.completed_between(today, today)} == {"Q1", "Q2"}
