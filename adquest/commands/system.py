"""Command handlers: character status, energy, logging, day cycle."""
from datetime import date, timedelta

from .. import paths
from ..core.config import load_config
from ..core.model import quest_focus
from ..core.state import load_state, save_state
from ..errors import QuestError
from ..render import colored, get_renderer, C_DIM, C_GREEN, C_RED, C_YELLOW


def cmd_status(args) -> None:
    """Display character status: level, XP, HP, MP, streak."""
    state = load_state()
    # Gather focused quests
    focused = [(k, v) for k, v in state["quests"].items()
               if v["status"] == "active" and quest_focus(v)]
    get_renderer().status(state, focused)


def cmd_drain(args) -> None:
    """Deduct HP and/or MP with a reason."""
    state = load_state()
    if args.hp < 0 or args.mp < 0:
        raise QuestError(colored("❌ HP and MP drain values must be positive.", C_RED))
    if not args.reason or not args.reason.strip():
        raise QuestError(colored("❌ Please provide a reason for the drain.", C_RED))
    state["hp"] = max(0, state["hp"] - args.hp)
    state["mp"] = max(0, state["mp"] - args.mp)
    save_state(state)
    print(f"💀 Drained: {colored(f'-{args.hp} HP', C_RED)}, {colored(f'-{args.mp} MP', C_RED)} ({args.reason})")
    if state["hp"] < 20:
        print(colored("  ⚠️  HP critically low! Consider resting.", C_RED))
    if state["mp"] < 20:
        print(colored("  ⚠️  MP critically low! Consider resting.", C_RED))


def cmd_rest(args) -> None:
    """Restore HP/MP using a predefined rest activity."""
    state = load_state()
    config = load_config()
    presets = config["rest_presets"]
    if args.activity not in presets:
        available = ", ".join(presets.keys())
        raise QuestError(colored(f"Unknown activity. Available: {available}", C_RED))
    preset = presets[args.activity]
    hp_change, mp_change = 0, 0
    for stat, val in [("hp", preset["hp"]), ("mp", preset["mp"])]:
        if isinstance(val, str) and val.startswith("="):
            old = state[stat]
            state[stat] = int(val[1:])
            if stat == "hp":
                hp_change = state[stat] - old
            else:
                mp_change = state[stat] - old
        else:
            old = state[stat]
            state[stat] = min(100, state[stat] + val)
            if stat == "hp":
                hp_change = state[stat] - old
            else:
                mp_change = state[stat] - old
    save_state(state)
    hp_str = f"+{hp_change}" if hp_change >= 0 else str(hp_change)
    mp_str = f"+{mp_change}" if mp_change >= 0 else str(mp_change)
    print(f"🧪 {args.activity}: {colored(f'{hp_str} HP', C_GREEN)}, {colored(f'{mp_str} MP', C_GREEN)}")
    print(f"   HP: {state['hp']}/100 | MP: {state['mp']}/100")


def cmd_log(args) -> None:
    """Archive today's completed quests to a log file, or view past logs."""
    # --- View mode: show past logs ---
    if getattr(args, "yesterday", False):
        target = (date.today() - timedelta(days=1)).isoformat()
        _show_log(target)
        return
    if getattr(args, "date", None):
        _show_log(args.date)
        return
    if getattr(args, "week", False):
        for i in range(6, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            _show_log(d, quiet=True)
        return

    # --- Write mode: archive today's completions ---
    state = load_state()
    today = date.today().isoformat()
    done_today = {k: v for k, v in state["quests"].items()
                  if v["status"] == "done" and v["completed"] and v["completed"][:10] == today}
    if not done_today:
        print(colored("No completed quests to log today.", C_DIM))
        return
    log_file = paths.LOGS_DIR / f"log-{today}.md"
    lines = []
    if not log_file.exists():
        lines.append(f"# Quest Log — {today}\n\n")
    for qid, q in sorted(done_today.items()):
        lines.append(f"- [x] **{qid}** — {q['desc']} (+{q['xp']} XP)\n")
    try:
        with open(log_file, "a") as f:
            f.writelines(lines)
    except OSError as e:
        print(colored(f"❌ Failed to write log file: {e}", C_RED))
        return
    # Move to history, keep last 50
    for qid in done_today:
        state["history"].append({"id": qid, **state["quests"].pop(qid)})
    state["history"] = state["history"][-50:]
    save_state(state)
    print(f"📝 Logged {len(done_today)} quest(s) to {colored(str(log_file), C_DIM)}")


def _show_log(target_date: str, quiet: bool = False) -> None:
    """Display a past log file by date."""
    log_file = paths.LOGS_DIR / f"log-{target_date}.md"
    if not log_file.exists():
        if not quiet:
            print(colored(f"No log found for {target_date}.", C_DIM))
        return
    with open(log_file, "r") as f:
        content = f.read().strip()
    print(content)
    if not quiet:
        print()


def auto_log_previous_day(state: dict) -> dict:
    """Log completed quests from previous day(s) that haven't been archived yet."""
    today = date.today().isoformat()
    # Find all completed quests that are NOT from today and still in quests dict
    to_log = {}
    for qid, q in list(state["quests"].items()):
        if q["status"] == "done" and q["completed"] and q["completed"][:10] != today:
            log_date = q["completed"][:10]
            if log_date not in to_log:
                to_log[log_date] = {}
            to_log[log_date][qid] = q

    if not to_log:
        return state

    for log_date, quests in sorted(to_log.items()):
        log_file = paths.LOGS_DIR / f"log-{log_date}.md"
        lines = []
        if not log_file.exists():
            lines.append(f"# Quest Log — {log_date}\n\n")
        for qid, q in sorted(quests.items()):
            lines.append(f"- [x] **{qid}** — {q['desc']} (+{q['xp']} XP)\n")
        try:
            with open(log_file, "a") as f:
                f.writelines(lines)
        except OSError as e:
            print(colored(f"⚠️  Failed to write log for {log_date}: {e}", C_YELLOW))
            continue
        # Move to history
        for qid in quests:
            state["history"].append({"id": qid, **state["quests"].pop(qid)})

    state["history"] = state["history"][-50:]
    total = sum(len(q) for q in to_log.values())
    dates = ", ".join(sorted(to_log.keys()))
    print(f"📝 Auto-logged {total} quest(s) from {dates}")
    return state


def cmd_newday(args) -> None:
    """Start a new day: archive previous, update streak, reset HP/MP."""
    state = load_state()
    # Auto-log previous day's completed quests before resetting
    state = auto_log_previous_day(state)
    # Streak logic
    last = state["last_quest_date"]
    if last:
        completed_yesterday = any(
            v["status"] == "done" and v["completed"] and v["completed"][:10] == last
            for v in state["quests"].values()
        ) or any(
            h["completed"] and h["completed"][:10] == last
            for h in state["history"]
        )
        if completed_yesterday:
            state["streak"] += 1
            print(f"🔥 Streak continues! Day {state['streak']}")
        else:
            state["streak"] = 0
            print(colored("❄️  Streak broken. Fresh start!", C_RED))
    else:
        state["streak"] = 1
        print("🔥 Streak started! Day 1")
    # Reset energy
    state["hp"] = 100
    state["mp"] = 100
    save_state(state)
    active = sum(1 for v in state["quests"].values() if v["status"] == "active")
    print(f"☀️  New day! HP/MP restored. {active} quest(s) carried over.")
