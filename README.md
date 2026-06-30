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

Requires Python 3.10+. Zero external dependencies.

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

All state lives in `~/.adquest/`:

```
~/.adquest/
├── state.json    # Character + quests
├── config.json   # Level table + rest presets
└── logs/
    └── log-2026-06-24.md
```

## Design Principles

- **Zero friction** — one command to add, one to complete
- **Micro-steps** — any quest >30min should be split into sub-quests
- **Energy awareness** — HP/MP tracking prevents burnout before it hits
- **ADHD-friendly** — focus limiter, idle nudges, type separation, visual feedback
- **Offline-first** — no network, no accounts, just local files
- **AI-optional** — daily tracking works without an AI assistant

## License

MIT
