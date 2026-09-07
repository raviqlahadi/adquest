"""CLI entry point — argument parsing and command dispatch."""
import argparse

import adquest.render as render
from . import __version__
from .commands.quests import (
    cmd_chain,
    cmd_drop,
    cmd_done,
    cmd_edit,
    cmd_focus,
    cmd_quest,
    cmd_reopen,
    cmd_sub,
    cmd_unfocus,
)
from .commands.system import cmd_drain, cmd_log, cmd_newday, cmd_rest, cmd_status
from .commands.views import cmd_idle, cmd_quests, cmd_summary, cmd_today
from .errors import QuestError
from .render import eprint_stderr_unexpected_error


def build_parser() -> argparse.ArgumentParser:
    """Construct the adquest argument parser."""
    parser = argparse.ArgumentParser(prog="adquest", description="⚔️ Gamified task management RPG")
    parser.add_argument("--format", choices=["ansi", "chat"], default="ansi", help="Output format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show debug output")
    parser.add_argument("--version", action="version", version=f"adquest {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("quest", help="Add a new quest")
    p.add_argument("desc", help="Quest description")
    p.add_argument("--xp", type=int, help="XP reward (default 10)")
    p.add_argument("--type", choices=["main", "side"], default="main", help="Quest type (default: main)")
    p.add_argument("--tag", help="Comma-separated tags (e.g. work,prakasa)")
    p.add_argument("--priority", choices=["high", "med", "low"], default="med", help="Priority level")

    p = sub.add_parser("sub", help="Add sub-quest")
    p.add_argument("parent", help="Parent quest ID (e.g. Q1)")
    p.add_argument("desc", help="Sub-quest description")
    p.add_argument("--xp", type=int, help="XP reward (default 10)")
    p.add_argument("--tag", help="Comma-separated tags")

    p = sub.add_parser("done", help="Complete a quest")
    p.add_argument("quest_id", help="Quest ID to complete")

    p = sub.add_parser("quests", help="List active quests")
    p.add_argument("--tag", help="Filter by tag")
    sub.add_parser("status", help="Show character status")

    p = sub.add_parser("drain", help="Deduct HP/MP")
    p.add_argument("hp", type=int, help="HP to drain")
    p.add_argument("mp", type=int, help="MP to drain")
    p.add_argument("reason", help="Reason for drain")

    p = sub.add_parser("rest", help="Restore HP/MP")
    p.add_argument("activity", help="Rest activity")

    p = sub.add_parser("log", help="Archive completed quests")
    p.add_argument("--date", help="Show log for a specific date (YYYY-MM-DD)")
    p.add_argument("--yesterday", action="store_true", help="Show yesterday's log")
    p.add_argument("--week", action="store_true", help="Show last 7 days of logs")

    p = sub.add_parser("chain", help="Link quests sequentially")
    p.add_argument("name", help="Chain name")
    p.add_argument("quests", nargs="+", help="Quest IDs in order")

    p = sub.add_parser("edit", help="Edit quest description or XP")
    p.add_argument("quest_id", help="Quest ID to edit")
    p.add_argument("--desc", help="New description")
    p.add_argument("--xp", type=int, help="New XP value")
    p.add_argument("--type", choices=["main", "side"], help="Change quest type")
    p.add_argument("--tag", help="Set tags (comma-separated)")
    p.add_argument("--priority", choices=["high", "med", "low"], help="Change priority")

    p = sub.add_parser("focus", help="Mark a quest as focused")
    p.add_argument("quest_id", help="Quest ID to focus")

    p = sub.add_parser("unfocus", help="Remove focus from a quest")
    p.add_argument("quest_id", help="Quest ID to unfocus")

    p = sub.add_parser("reopen", help="Reopen a completed quest")
    p.add_argument("quest_id", help="Quest ID to reopen")

    sub.add_parser("newday", help="Start a new day")

    p = sub.add_parser("idle", help="Show quests idle for N+ days")
    p.add_argument("--days", type=int, default=3, help="Idle threshold in days (default: 3)")

    sub.add_parser("today", help="Show focused quests + created today")

    p = sub.add_parser("drop", help="Drop/abandon a quest (no XP)")
    p.add_argument("quest_id", help="Quest ID to drop")
    p.add_argument("reason", nargs="?", default=None, help="Reason for dropping")

    sub.add_parser("summary", help="Show daily summary")

    return parser


def dispatch(args: argparse.Namespace) -> None:
    """Route a parsed command to its handler."""
    match args.command:
        case "quest": cmd_quest(args)
        case "sub": cmd_sub(args)
        case "done": cmd_done(args)
        case "quests": cmd_quests(args)
        case "status": cmd_status(args)
        case "drain": cmd_drain(args)
        case "rest": cmd_rest(args)
        case "log": cmd_log(args)
        case "chain": cmd_chain(args)
        case "edit": cmd_edit(args)
        case "reopen": cmd_reopen(args)
        case "newday": cmd_newday(args)
        case "focus": cmd_focus(args)
        case "unfocus": cmd_unfocus(args)
        case "idle": cmd_idle(args)
        case "today": cmd_today(args)
        case "drop": cmd_drop(args)
        case "summary": cmd_summary(args)


def main() -> None:
    """CLI entry point — parse arguments and dispatch to command handlers."""
    parser = build_parser()
    args = parser.parse_args()
    render.FORMAT = args.format
    render.VERBOSE = args.verbose
    if not args.command:
        parser.print_help()
        return

    try:
        dispatch(args)
    except QuestError as e:
        print(e)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print()
        raise SystemExit(0)
    except Exception as e:
        eprint_stderr_unexpected_error(e)
        raise SystemExit(1)
