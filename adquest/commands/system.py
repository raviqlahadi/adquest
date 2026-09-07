"""Command handlers: character status, energy, logging, day cycle."""
from datetime import date, timedelta

from .. import paths
from ..core.config import load_config
from ..core.model import quest_focus
from ..errors import QuestError
from ..render import colored, get_renderer, C_DIM, C_GREEN, C_RED, C_YELLOW
from .. import store as store_mod


def cmd_status(args) -> None:
    """Display character status: level, XP, HP, MP, streak."""
    with store_mod.open_store() as store:
        player = store.get_player()
        # Gather focused quests
        focused = [(qid, q) for qid, q in store.list_quests(status="active") if quest_focus(q)]
    # Renderer expects the v1 character-sheet dict shape
    get_renderer().status(player, focused)


def cmd_drain(args) -> None:
    """Deduct HP and/or MP with a reason."""
    if args.hp < 0 or args.mp < 0:
        raise QuestError(colored("❌ HP and MP drain values must be positive.", C_RED))
    if not args.reason or not args.reason.strip():
        raise QuestError(colored("❌ Please provide a reason for the drain.", C_RED))
    with store_mod.open_store() as store:
        player = store.get_player()
        player["hp"] = max(0, player["hp"] - args.hp)
        player["mp"] = max(0, player["mp"] - args.mp)
        store.update_player(player)
        store.commit()
        hp, mp = player["hp"], player["mp"]
    print(f"💀 Drained: {colored(f'-{args.hp} HP', C_RED)}, {colored(f'-{args.mp} MP', C_RED)} ({args.reason})")
    if hp < 20:
        print(colored("  ⚠️  HP critically low! Consider resting.", C_RED))
    if mp < 20:
        print(colored("  ⚠️  MP critically low! Consider resting.", C_RED))


def cmd_rest(args) -> None:
    """Restore HP/MP using a predefined rest activity."""
    config = load_config()
    presets = config["rest_presets"]
    if args.activity not in presets:
        available = ", ".join(presets.keys())
        raise QuestError(colored(f"Unknown activity. Available: {available}", C_RED))
    preset = presets[args.activity]
    with store_mod.open_store() as store:
        player = store.get_player()
        hp_change, mp_change = 0, 0
        for stat, val in [("hp", preset["hp"]), ("mp", preset["mp"])]:
            if isinstance(val, str) and val.startswith("="):
                old = player[stat]
                player[stat] = int(val[1:])
                if stat == "hp":
                    hp_change = player[stat] - old
                else:
                    mp_change = player[stat] - old
            else:
                old = player[stat]
                player[stat] = min(100, player[stat] + val)
                if stat == "hp":
                    hp_change = player[stat] - old
                else:
                    mp_change = player[stat] - old
        store.update_player(player)
        store.commit()
        hp, mp = player["hp"], player["mp"]
    hp_str = f"+{hp_change}" if hp_change >= 0 else str(hp_change)
    mp_str = f"+{mp_change}" if mp_change >= 0 else str(mp_change)
    print(f"🧪 {args.activity}: {colored(f'{hp_str} HP', C_GREEN)}, {colored(f'{mp_str} MP', C_GREEN)}")
    print(f"   HP: {hp}/100 | MP: {mp}/100")


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
    today = date.today().isoformat()
    with store_mod.open_store() as store:
        done_today = [(qid, q) for qid, q in store.list_quests(status="done")
                      if q["completed"] and q["completed"][:10] == today]
        if not done_today:
            print(colored("No completed quests to log today.", C_DIM))
            return
        log_file = paths.LOGS_DIR / f"log-{today}.md"
        lines = []
        if not log_file.exists():
            lines.append(f"# Quest Log — {today}\n\n")
        for qid, q in sorted(done_today):
            lines.append(f"- [x] **{qid}** — {q['desc']} (+{q['xp']} XP)\n")
        try:
            with open(log_file, "a") as f:
                f.writelines(lines)
        except OSError as e:
            print(colored(f"❌ Failed to write log file: {e}", C_RED))
            return
        # Move to history (cap handled by the store, v1 parity)
        for qid, _ in done_today:
            store.move_to_history(qid)
        store.commit()
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


def auto_log_previous_day(store) -> None:
    """Log completed quests from previous day(s) that haven't been archived yet."""
    today = date.today().isoformat()
    # Find all completed quests that are NOT from today and still in the active pool
    to_log = {}
    for qid, q in store.list_quests(status="done"):
        if q["completed"] and q["completed"][:10] != today:
            log_date = q["completed"][:10]
            to_log.setdefault(log_date, []).append((qid, q))

    if not to_log:
        return

    for log_date, quests in sorted(to_log.items()):
        log_file = paths.LOGS_DIR / f"log-{log_date}.md"
        lines = []
        if not log_file.exists():
            lines.append(f"# Quest Log — {log_date}\n\n")
        for qid, q in sorted(quests):
            lines.append(f"- [x] **{qid}** — {q['desc']} (+{q['xp']} XP)\n")
        try:
            with open(log_file, "a") as f:
                f.writelines(lines)
        except OSError as e:
            print(colored(f"⚠️  Failed to write log for {log_date}: {e}", C_YELLOW))
            continue
        # Move to history
        for qid, _ in quests:
            store.move_to_history(qid)

    total = sum(len(q) for q in to_log.values())
    dates = ", ".join(sorted(to_log.keys()))
    print(f"📝 Auto-logged {total} quest(s) from {dates}")


def cmd_newday(args) -> None:
    """Start a new day: archive previous, update streak, reset HP/MP."""
    with store_mod.open_store() as store:
        # Auto-log previous day's completed quests before resetting
        auto_log_previous_day(store)
        player = store.get_player()
        # Streak logic
        last = player["last_quest_date"]
        if last:
            completed_on_last = any(
                q["completed"] and q["completed"][:10] == last
                for _, q in store.list_quests(status="done")
            ) or any(
                h["completed"] and h["completed"][:10] == last
                for _, h in store.get_history()
            )
            if completed_on_last:
                player["streak"] += 1
                print(f"🔥 Streak continues! Day {player['streak']}")
            else:
                player["streak"] = 0
                print(colored("❄️  Streak broken. Fresh start!", C_RED))
        else:
            player["streak"] = 1
            print("🔥 Streak started! Day 1")
        # Reset energy
        player["hp"] = 100
        player["mp"] = 100
        store.update_player(player)
        store.commit()
        active = len(store.list_quests(status="active"))
    print(f"☀️  New day! HP/MP restored. {active} quest(s) carried over.")
