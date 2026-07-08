# STEERING.md — adquest

## Vision

adquest is a personal CLI tool that gamifies daily task management with RPG mechanics. It exists to provide external structure, micro-step decomposition, and dopamine hits for an ADHD brain — replacing the need for an AI assistant in routine task tracking.

## Principles

1. **Zero friction** — Adding a quest should be faster than writing a sticky note
2. **Visible progress** — Every action gives feedback: XP, level-ups, streaks, emoji
3. **No external deps** — Python stdlib only. Runs anywhere Python 3.10+ exists
4. **Single source of truth** — All state lives in `~/.adquest/state.json`
5. **Git-trackable data** — State directory is independent from source, but diffable
6. **ADHD-friendly** — Short commands, auto-IDs, color output, celebration on wins

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Single-file v1 | Minimizes overhead; split later when complexity warrants |
| JSON state | Human-readable, git-diffable, stdlib `json` module |
| Auto-incrementing IDs (Q1, Q2...) | No cognitive load to name tasks |
| ANSI color via stdlib | No curses, no rich — just `\033[` escape codes |
| argparse for CLI | Stdlib, subcommand support, good enough |
| Config separate from state | Allows tuning without touching live data |
| Symlink in ~/.local/bin | Standard user-local PATH entry on Linux |

## Scope — v1

### In Scope
- All 13 core commands (quest, sub, done, quests, status, drain, rest, log, chain, edit, reopen, newday)
- Level progression (10 levels)
- HP/MP energy system with rest presets
- Streak tracking
- Quest chains (sequential dependencies)
- Daily log archival (markdown)
- Auto-log on newday (archives previous day's completed quests before reset)
- Quest editing (description and XP)
- Quest reopen (reverses XP, restores from history)
- Colored terminal output with emoji

### Out of Scope (future)
- TUI/interactive mode
- Multiplayer/shared quests
- Database backend
- Web interface
- Notifications/reminders
- Weekly/monthly stats and reports
- Tags/priority filtering
- Buff system (streak/rest bonuses)
- Quest energy cost (auto-drain HP/MP on completion, based on XP value or --cost flag)

## File Layout

```
~/projects/adquest/
├── STEERING.md          # This file
├── SPEC.md              # Design spec + task breakdown
└── adquest.py           # Implementation (entry point)

~/.adquest/
├── state.json           # Live character + quest state
├── config.json          # Customizable presets and level table
└── logs/
    └── log-YYYY-MM-DD.md  # Daily archives
```

## Constraints

- Python 3.10+ (match statements OK)
- Zero external packages
- Single file for v1
- All output to stdout with ANSI color
- State mutations are atomic (read → modify → write)
