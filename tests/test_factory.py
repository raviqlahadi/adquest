"""Backend selection wiring (Q197.4): precedence chain + factory.

Resolution tests are pure (no connections). The one construction test
needs the local dev cluster and skips when it's unreachable.
"""

import json
import os
import re

import pytest

import adquest.paths as paths
import adquest.store as store_mod
from adquest.errors import QuestError
from adquest.store import FileStore

try:
    from adquest.store.postgres import PostgresStore
    _HAS_POSTGRES = True
except ImportError:
    _HAS_POSTGRES = False

TEST_DSN = "host=/tmp port=5433 dbname=adquest_test"


@pytest.fixture(autouse=True)
def _clean_selection(monkeypatch):
    """Isolate env, config file, and CLI overrides for every test."""
    monkeypatch.delenv("ADQUEST_BACKEND", raising=False)
    monkeypatch.delenv("ADQUEST_DSN", raising=False)
    monkeypatch.setattr(store_mod, "_cli_backend", None)
    monkeypatch.setattr(store_mod, "_cli_dsn", None)
    yield


def write_config(monkeypatch, tmp_path, **keys):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(keys))
    monkeypatch.setattr(paths, "CONFIG_FILE", cfg_file)


def test_default_is_file_backend():
    assert store_mod.resolve_backend() == ("file", None)
    assert isinstance(store_mod.open_store(), FileStore)


def test_cli_overrides_env_and_config(monkeypatch, tmp_path):
    monkeypatch.setenv("ADQUEST_BACKEND", "postgres")
    monkeypatch.setenv("ADQUEST_DSN", "dbname=env-dsn")
    write_config(monkeypatch, tmp_path, backend="postgres", postgres_dsn="dbname=config-dsn")
    store_mod.set_cli_overrides("file", "dbname=cli-dsn")
    assert store_mod.resolve_backend() == ("file", "dbname=cli-dsn")
    assert isinstance(store_mod.open_store(), FileStore)


def test_env_beats_config(monkeypatch, tmp_path):
    monkeypatch.setenv("ADQUEST_BACKEND", "file")
    write_config(monkeypatch, tmp_path, backend="postgres", postgres_dsn="dbname=config-dsn")
    assert store_mod.resolve_backend() == ("file", "dbname=config-dsn")


def test_config_provides_backend_and_dsn(monkeypatch, tmp_path):
    write_config(monkeypatch, tmp_path, backend="postgres", postgres_dsn="dbname=config-dsn")
    assert store_mod.resolve_backend() == ("postgres", "dbname=config-dsn")


def test_dsn_falls_back_independently(monkeypatch, tmp_path):
    # backend from env, dsn from config — sources may contribute partially
    monkeypatch.setenv("ADQUEST_BACKEND", "postgres")
    write_config(monkeypatch, tmp_path, postgres_dsn="dbname=config-dsn")
    assert store_mod.resolve_backend() == ("postgres", "dbname=config-dsn")


def test_unknown_backend_from_config_raises(monkeypatch, tmp_path):
    write_config(monkeypatch, tmp_path, backend="sqlite")
    with pytest.raises(QuestError, match="Unknown backend 'sqlite'"):
        store_mod.open_store()


def test_unknown_backend_from_env_raises(monkeypatch):
    monkeypatch.setenv("ADQUEST_BACKEND", "oracle")
    with pytest.raises(QuestError, match="Unknown backend 'oracle'"):
        store_mod.open_store()


@pytest.mark.skipif(not _HAS_POSTGRES, reason="psycopg not installed")
def test_open_store_constructs_postgres(monkeypatch):
    dsn = os.environ.get("ADQUEST_TEST_DSN", TEST_DSN)
    if not re.search(r"dbname=[^ ]*_test(?: |$)", dsn + " "):
        pytest.fail("factory test refuses non-test database — dbname must end with '_test'")
    monkeypatch.setenv("ADQUEST_BACKEND", "postgres")
    monkeypatch.setenv("ADQUEST_DSN", dsn)
    try:
        store = store_mod.open_store()
    except QuestError as e:
        if "Cannot reach" in str(e):
            pytest.skip(f"dev cluster unreachable: {e}")
        raise
    with store:
        assert isinstance(store, PostgresStore)
