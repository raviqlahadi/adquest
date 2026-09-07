# STEERING.md — adquest

## Vision

adquest is a personal CLI tool that gamifies daily task management with RPG mechanics. It exists to provide external structure, micro-step decomposition, and dopamine hits for an ADHD brain. v1 replaced the need for an AI assistant in routine task tracking; v2 makes the state portable — one saga, every device, backed by a real database.

## Principles

1. **Zero friction** — Adding a quest should be faster than writing a sticky note
2. **Visible progress** — Every action gives feedback: XP, level-ups, streaks, emoji
3. **Stdlib core** — The file backend runs anywhere Python 3.10+ exists, zero dependencies. Heavy features (PostgreSQL) ride in as *optional extras* (`adquest[postgres]`), imported lazily so they cost nothing when unused
4. **One active backend** — All state lives in exactly one place at a time: `~/.adquest/state.json` (file backend) or the configured PostgreSQL database (postgres backend). No dual-write, no split-brain
5. **Parity above cleverness** — Every backend must pass the identical contract suite (`tests/contract/test_parity.py`). Behavior differences between backends are bugs, not features
6. **ADHD-friendly** — Short commands, auto-IDs, color output, celebration on wins
7. **Recoverable by design** — File state is git-synced; the DB is pg_dump'd daily; migration tooling can rebuild either from the other plus git history

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Package split (core/render/commands/store/cli) | v2 complexity warranted it; `adquest.py` shim kept for entry-point compat |
| QuestStore ABC contract | Copy-on-read, commit-boundary persistence, dict boundary with v1 field names — the seam that makes backends interchangeable |
| JSONB document rows (not typed columns) | Quest dicts are schema-elastic (optional fields, forward-compat); dict-boundary contract makes JSONB round-trip byte-exact; queried attributes stay SQL-addressable via expression indexes |
| Identity columns for ordering | v1 dict insertion order must survive SQL; `ord`/`hord` give race-free monotonic ordering across machines |
| Session advisory lock | The networked equivalent of FileStore's flock — transactions alone can't stop lost updates between devices |
| Uncapped history in Postgres | v1's 50-entry cap evicted ~127 quests over 46 days; networked backends keep everything (contract rule 4) |
| Lazy psycopg import | `import adquest` must never require the optional extra |
| Backend selection: CLI > env > config > file | `--backend`/`--dsn` flags beat `$ADQUEST_BACKEND`/`$ADQUEST_DSN` beat config.json keys (`backend`/`postgres_dsn`) beat the default |
| argparse + stdlib ANSI | Still sufficient; unchanged from v1 |
| Auto-incrementing IDs (Q1, Q2...) | Unchanged — no cognitive load |

## Scope

### In Scope (v2)
- All v1 commands, unchanged in behavior
- FileStore (v1 semantics preserved byte-compatibly, incl. flock and 50-entry history cap)
- PostgresStore (schema bootstrap, advisory lock, uncapped history, JSONB rows)
- Backend selection (CLI flags, env vars, config.json)
- Contract/parity test suite running every scenario against every backend
- Migration tooling: `~/tools/adquest-migrate` — state.json → Postgres, git-snapshot backfill of evicted history, built-in parity verification, `*_test` database guardrails

### Out of Scope (still)
- TUI/interactive mode
- Multiplayer/shared quests
- Web interface
- Notifications/reminders
- Weekly/monthly stats and reports
- Buff system
- Quest energy cost

## File Layout

```
~/projects/adquest/
├── STEERING.md            # This file
├── SPEC.md                # v1 design spec (historical)
├── adquest/
│   ├── cli.py             # argparse + dispatch
│   ├── core/              # model, config, progression
│   ├── commands/          # quest/system/view handlers
│   ├── render/            # ansi + chat formatters
│   ├── store/             # QuestStore ABC, FileStore, PostgresStore
│   └── errors.py
├── tests/
│   ├── test_adquest.py    # v1 behavior suite (file backend)
│   ├── test_factory.py    # backend selection wiring
│   └── contract/
│       └── test_parity.py # identical scenarios × every backend
└── pyproject.toml         # extras: dev (pytest), postgres (psycopg)

~/.adquest/                # file backend (git-synced)
├── state.json             # Live character + quest state
├── state.json.bak
├── config.json            # Levels, presets, backend selection
└── logs/

~/tools/adquest-migrate    # migration + backfill tool (outside the repo)
```

## Operations

- **Dev/test database**: local user-space cluster, databases ending in `_test` ONLY — the test suite refuses any other `dbname` (it drops schemas). See `tests/contract/test_parity.py`
- **VPS**: Postgres on localhost only, reached via `pg-tunnel` (SSH). Daily pg_dump cron, 14-day retention
- **Re-sync devices**: `ADQUEST_DSN=... adquest-migrate --backfill-git --reset` rebuilds the DB from the live file + all git snapshots (newest-known-wins)

## Constraints

- Python 3.10+ (match statements OK)
- Core: zero external packages; `postgres` extra: psycopg only
- All output to stdout with ANSI color
- Atomicity: file backend = flock + write; postgres backend = advisory lock + transactions
- Test databases must end in `_test` — the suite enforces this
