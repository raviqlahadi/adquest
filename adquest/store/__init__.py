"""Storage backends for adquest.

``open_store()`` is the single seam commands use to obtain a store.

Backend selection precedence (Q197.4):

    CLI --backend / --dsn  >  $ADQUEST_BACKEND / $ADQUEST_DSN  >
    config.json ("backend" / "postgres_dsn" keys)  >  default: file

psycopg is an optional extra — the postgres branch imports lazily so
file-only installs never need it.
"""
import os

from ..core.config import load_config
from ..errors import QuestError
from .base import QuestStore
from .file import FileStore, DEFAULT_STATE, HISTORY_CAP

__all__ = [
    "QuestStore", "FileStore", "DEFAULT_STATE", "HISTORY_CAP",
    "open_store", "resolve_backend", "set_cli_overrides",
]

# CLI-level overrides, set once by cli.main() after parsing (same
# pattern as render.FORMAT). Never touched by commands.
_cli_backend: str | None = None
_cli_dsn: str | None = None


def set_cli_overrides(backend: str | None, dsn: str | None) -> None:
    """Install CLI flag values as highest-precedence backend selection."""
    global _cli_backend, _cli_dsn
    _cli_backend, _cli_dsn = backend, dsn


def resolve_backend() -> tuple[str, str | None]:
    """Resolve (backend, dsn) across the full precedence chain.

    The DSN chain is independent of the backend chain — it only matters
    when 'postgres' is selected. All sources may also contribute partial
    information (e.g. backend from env, dsn from config).
    """
    config = load_config()
    backend = (
        _cli_backend
        or os.environ.get("ADQUEST_BACKEND")
        or config.get("backend")
        or "file"
    )
    dsn = (
        _cli_dsn
        or os.environ.get("ADQUEST_DSN")
        or config.get("postgres_dsn")
        or None
    )
    return backend, dsn


def open_store() -> QuestStore:
    """Return the configured store backend."""
    backend, dsn = resolve_backend()
    if backend == "file":
        return FileStore()
    if backend == "postgres":
        from .postgres import PostgresStore  # lazy — psycopg is optional
        return PostgresStore(dsn)
    raise QuestError(f"Unknown backend {backend!r} (expected 'file' or 'postgres')")
