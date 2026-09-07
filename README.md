# ⚔️ adquest

A gamified task management CLI with RPG mechanics. Built for ADHD brains that thrive on structure, novelty, and dopamine hits.

## Install

### Option A: Symlink (dev)

```bash
git clone https://github.com/youruser/adquest.git ~/projects/adquest
ln -sf ~/projects/adquest/adquest.py ~/.local/bin/adquest
chmod +x ~/projects/adquest/adquest.py
```

### Option B: pip install

```bash
pip install git+https://github.com/youruser/adquest.git
```

This creates the `adquest` command in your PATH automatically. Works on Linux, macOS, and Windows.

Requires Python 3.10+. The core has **zero external dependencies** — the optional PostgreSQL backend installs as an extra:

```bash
pip install 'adquest[postgres]'   # or: uv sync --extra postgres
```

## Usage

```bash
# Add a quest
adquest quest "Fix the auth bug" --xp 15

# Add a side quest (personal/optional)
adquest quest "Set up home server" --xp 10 --type side

# Add with priority and tags
adquest quest "Hotfix prod crash" --xp 20 --priority high --tag backend,urgent

# Add sub-quests
adquest sub Q1 "Reproduce locally" --xp 5
adquest sub Q1 "Write the fix" --xp 10

# Complete a quest
adquest done Q1.1

# Focus on a quest (max 3 at a time)
adquest focus Q1
adquest unfocus Q1

# View active quests (split by main/side)
adquest quests

# Filter quests by tag
adquest quests --tag backend

# Today's view (focused + created today)
adquest today

# Show idle quests (older than N days)
adquest idle
adquest idle --days 7

# Check your stats
adquest status

# Edit a quest
adquest edit Q1 --desc "Fix the OAuth bug" --xp 20
adquest edit Q1 --type side
adquest edit Q1 --tag refactor,auth
adquest edit Q1 --priority high

# Reopen a completed quest (reverses XP)
adquest reopen Q3

# Track energy
adquest drain 5 20 "deep debugging session"
adquest rest lunch

# Link quests in sequence
adquest chain "auth-fix" Q1 Q2 Q3

# Archive completed quests to daily log
adquest log

# Start a new day (auto-logs yesterday, resets energy, updates streak)
adquest newday
```

## Commands

| Command | Description |
|---------|-------------|
| `quest "desc" [--xp N] [--type main\|side] [--tag t1,t2] [--priority high\|med\|low]` | Add quest |
| `sub Q1 "desc" [--xp N] [--tag t1,t2]` | Add sub-quest under parent |
| `done Q1` | Complete quest, award XP |
| `quests [--tag TAG]` | List active quests (grouped by type) |
| `status` | Level, XP, HP/MP, streak, focus |
| `focus Q1` | Mark quest as actively in-progress (max 3) |
| `unfocus Q1` | Remove focus from quest |
| `today` | Show focused quests + quests added today |
| `idle [--days N]` | Show quests idle for N+ days (default 3) |
| `edit Q1 [--desc] [--xp] [--type] [--tag] [--priority]` | Edit quest fields |
| `reopen Q1` | Reopen completed quest (reverses XP) |
| `drain <hp> <mp> "reason"` | Deduct energy |
| `rest <activity>` | Restore energy from preset |
| `chain "name" Q1 Q2...` | Link quests sequentially |
| `log` | Archive done quests to markdown |
| `newday` | New day reset (auto-logs previous day) |

## Quest Types

Quests are split into two lanes:

- **⚔️ Main** — work, priorities, things that pay the bills (default)
- **🌙 Side** — personal projects, errands, exploration

```
━━━ ⚔️ Main Quests ━━━
  🔶 Q25 — UAT support (+15 XP) ▲ [FOCUS] [prakasa, uat]
  ⬜ Q26 — Follow up ENV fix (+5 XP)

━━━ 🌙 Side Quests ━━━
  ⬜ Q5  — Free parking form (+5 XP)
```

## Focus System

Mark what you're currently working on. Max 3 focused quests — an ADHD guard rail.

```bash
adquest focus Q25    # 🔶 marks as active
adquest unfocus Q25  # ⬜ back to queued
```

Focused quests appear in `adquest status` and `adquest today`.

## Priority

- `--priority high` → shows ▲ (red) in quest list
- `--priority med` → default, no indicator
- `--priority low` → shows ▽ (dim)

## Tags

Label quests for filtering:

```bash
adquest quest "Deploy v2" --tag backend,deploy
adquest quests --tag backend   # only shows tagged quests
adquest edit Q1 --tag new,tags # replaces tags
```

## Energy Presets

| Activity | HP | MP |
|----------|----|----|
| lunch | +20 | +30 |
| coffee | +0 | +10 |
| nap | +10 | +20 |
| sleep | =100 | =100 |
| gaming | +5 | +15 |
| shower | +15 | +10 |
| dj | +0 | +20 |
| sprint | +15 | +25 |

## Progression

| Level | Title | XP Required |
|-------|-------|-------------|
| 1 | Apprentice of the Forge | 100 |
| 2 | Journeyman Codewright | 150 |
| 3 | Adept of the Iron Stack | 200 |
| 4 | Wardkeeper | 300 |
| 5 | Runesmith | 400 |
| 6 | Archon of Systems | 500 |
| 7 | Voidwalker | 650 |
| 8 | Mythral Architect | 800 |
| 9 | Elder of the Obsidian Guild | 1000 |
| 10 | Ascendant | ∞ |

## Data

Default state lives in `~/.adquest/`:

```
~/.adquest/
├── state.json    # Character + quests (file backend)
├── config.json   # Level table + rest presets + backend selection
└── logs/
    └── log-2026-06-24.md
```

## Storage Backends

Two interchangeable backends, one contract — every command behaves identically on both (enforced by the parity test suite):

| Backend | State location | Concurrency | History cap |
|---------|---------------|-------------|-------------|
| `file` (default) | `~/.adquest/state.json` | flock (single machine) | 50 entries |
| `postgres` | PostgreSQL database | session advisory lock (multi-device) | unlimited |

**Selection precedence** (highest wins):

```bash
adquest --backend postgres --dsn "postgresql://user:pass@host:5432/adquest" status  # 1. CLI flags
export ADQUEST_BACKEND=postgres ADQUEST_DSN="postgresql://..."                      # 2. env vars
```
```jsonc
// 3. ~/.adquest/config.json
{ "backend": "postgres", "postgres_dsn": "postgresql://..." }
```

psycopg imports lazily — the file backend never needs it.

**Migrating from the file backend** (`~/tools/adquest-migrate`, verification built in):

```bash
# Dry run, then full migration with parity check
~/tools/adquest-migrate --dry-run
~/tools/adquest-migrate --reset

# Resurrect quests evicted by v1's 50-entry history cap from git snapshots
~/tools/adquest-migrate --backfill-git --reset
```

**Multi-device setup**: run Postgres on a private host (bound to localhost, reached via SSH tunnel — see `postgres-backend-setup.md` in the knowledge vault), point each device's `config.json` at the tunnel, and every machine shares one live saga.

## Design Principles

- **Zero friction** — one command to add, one to complete
- **Micro-steps** — any quest >30min should be split into sub-quests
- **Energy awareness** — HP/MP tracking prevents burnout before it hits
- **ADHD-friendly** — focus limiter, idle nudges, type separation, visual feedback
- **Offline-first** — the default file backend needs no network and no accounts; the optional Postgres backend is self-hosted
- **Recoverable** — git-synced state, daily DB dumps, and migration tooling that verifies parity on every run
- **AI-optional** — daily tracking works without an AI assistant

## License

MIT
