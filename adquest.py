#!/usr/bin/env python3
"""adquest — Gamified task management RPG CLI."""

import argparse
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

# --- Paths ---
DATA_DIR = Path.home() / ".adquest"
STATE_FILE = DATA_DIR / "state.json"
CONFIG_FILE = DATA_DIR / "config.json"
LOGS_DIR = DATA_DIR / "logs"

# --- Format ---
FORMAT = "ansi"  # global, set by --format flag
VERBOSE = False  # global, set by --verbose flag


def vprint(msg: str) -> None:
    """Print a message only when verbose mode is active."""
    if VERBOSE:
        print(colored(f"  [debug] {msg}", C_DIM))


# --- Colors ---
C_RESET = "\033[0m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"


def colored(text: str, color: str) -> str:
    """Wrap text in ANSI color codes. Returns plain text in chat format."""
    if FORMAT == "chat":
        return text
    return f"{color}{text}{C_RESET}"


def bar(current: int, maximum: int, width: int = 20) -> str:
    """Render a progress bar with filled/empty blocks."""
    if FORMAT == "chat":
        return f"{current}/{maximum}"
    filled = int(current / maximum * width) if maximum else 0
    return f"{colored('█' * filled, C_GREEN)}{colored('░' * (width - filled), C_DIM)}"


# --- Config ---
DEFAULT_CONFIG = {
    "levels": [
        {"level": 1, "title": "Apprentice of the Forge", "xp_next": 100},
        {"level": 2, "title": "Journeyman Codewright", "xp_next": 150},
        {"level": 3, "title": "Adept of the Iron Stack", "xp_next": 200},
        {"level": 4, "title": "Wardkeeper", "xp_next": 300},
        {"level": 5, "title": "Runesmith", "xp_next": 400},
        {"level": 6, "title": "Archon of Systems", "xp_next": 500},
        {"level": 7, "title": "Voidwalker", "xp_next": 650},
        {"level": 8, "title": "Mythral Architect", "xp_next": 800},
        {"level": 9, "title": "Elder of the Obsidian Guild", "xp_next": 1000},
        {"level": 10, "title": "Ascendant", "xp_next": None},
    ],
    "rest_presets": {
        "lunch": {"hp": 20, "mp": 30},
        "coffee": {"hp": 0, "mp": 10},
        "nap": {"hp": 10, "mp": 20},
        "sleep": {"hp": "=100", "mp": "=100"},
        "gaming": {"hp": 5, "mp": 15},
        "shower": {"hp": 15, "mp": 10},
        "dj": {"hp": 0, "mp": 20},
        "sprint": {"hp": 15, "mp": 25},
    },
}


def load_config() -> dict:
    """Load config from disk, falling back to defaults on error."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(colored(f"⚠️  Config corrupted ({e}). Using defaults.", C_YELLOW))
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


def save_config(config: dict) -> None:
    """Write config to disk. Exits on failure."""
    try:
        CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")
    except OSError as e:
        print(colored(f"❌ Failed to save config: {e}", C_RED))
        sys.exit(1)


# --- State ---
DEFAULT_STATE = {
    "level": 1,
    "title": "Apprentice of the Forge",
    "xp": 0,
    "xp_next": 100,
    "hp": 100,
    "mp": 100,
    "streak": 0,
    "last_quest_date": None,
    "quests": {},
    "chains": {},
    "history": [],
    "buffs": [],
    "achievements": [],
}


def ensure_dirs() -> None:
    """Create data and logs directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    """Load state from disk. Falls back to backup or defaults on corruption."""
    ensure_dirs()
    if STATE_FILE.exists():
        vprint(f"Loading state from {STATE_FILE}")
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError as e:
            # Try backup before giving up
            backup = STATE_FILE.with_suffix(".json.bak")
            if backup.exists():
                print(colored(f"⚠️  State corrupted ({e}). Restoring from backup.", C_YELLOW))
                try:
                    return json.loads(backup.read_text())
                except (json.JSONDecodeError, OSError):
                    pass
            print(colored(f"❌ State file corrupted and no valid backup. Starting fresh.", C_RED))
            return DEFAULT_STATE.copy()
        except OSError as e:
            print(colored(f"❌ Cannot read state file: {e}", C_RED))
            sys.exit(1)
    return DEFAULT_STATE.copy()


def save_state(state: dict) -> None:
    """Save state to disk with automatic backup. Exits on failure."""
    ensure_dirs()
    # Backup current state before overwriting
    if STATE_FILE.exists():
        try:
            backup = STATE_FILE.with_suffix(".json.bak")
            backup.write_text(STATE_FILE.read_text())
            vprint(f"Backup saved to {backup}")
        except OSError:
            pass  # Non-fatal — proceed with save
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
        vprint(f"State saved to {STATE_FILE}")
    except OSError as e:
        print(colored(f"❌ Failed to save state: {e}", C_RED))
        sys.exit(1)


# --- Level-up ---
def check_levelup(state: dict, config: dict) -> None:
    """Check and apply level-ups if XP exceeds threshold."""
    while state["xp_next"] is not None and state["xp"] >= state["xp_next"]:
        state["xp"] -= state["xp_next"]
        state["level"] += 1
        lvl_info = next((l for l in config["levels"] if l["level"] == state["level"]), None)
        if lvl_info:
            state["title"] = lvl_info["title"]
            state["xp_next"] = lvl_info["xp_next"]
        print()
        print(colored("╔══════════════════════════════════════╗", C_YELLOW))
        print(colored("║       ⚡ L E V E L   U P ⚡          ║", C_YELLOW))
        print(colored("╠══════════════════════════════════════╣", C_YELLOW))
        print(colored(f"║  Level {state['level']}: {state['title']:<27}║", C_YELLOW))
        print(colored("╚══════════════════════════════════════╝", C_YELLOW))
        print()


# --- ID helpers ---
def next_quest_id(state: dict) -> str:
    """Generate the next unique quest ID (checks active + history)."""
    top_ids = [k for k in state["quests"] if "." not in k]
    hist_ids = [h["id"] for h in state.get("history", []) if "." not in h["id"]]
    all_ids = top_ids + hist_ids
    if not all_ids:
        return "Q1"
    nums = [int(k[1:]) for k in all_ids]
    return f"Q{max(nums) + 1}"


def next_sub_id(state: dict, parent_id: str) -> str | None:
    """Generate the next sub-quest ID under a parent (e.g. Q1.3)."""
    parent = state["quests"].get(parent_id)
    if not parent:
        return None
    return f"{parent_id}.{len(parent['children']) + 1}"


# --- Commands ---
def quest_type(quest: dict) -> str:
    """Get quest type with backward compat — defaults to 'main'."""
    return quest.get("type", "main")


def quest_focus(quest: dict) -> bool:
    """Get quest focus with backward compat — defaults to False."""
    return quest.get("focus", False)


def cmd_quest(args: argparse.Namespace) -> None:
    """Add a new top-level quest."""
    state = load_state()
    # Input validation
    if not args.desc or not args.desc.strip():
        print(colored("❌ Quest description cannot be empty.", C_RED))
        return
    if args.xp is not None and args.xp < 0:
        print(colored("❌ XP must be a positive number.", C_RED))
        return
    qid = next_quest_id(state)
    xp = args.xp or 10
    qtype = args.type or "main"
    tags = [t.strip() for t in args.tag.split(",")] if args.tag else []
    priority = args.priority or "med"
    state["quests"][qid] = {
        "desc": args.desc,
        "xp": xp,
        "status": "active",
        "type": qtype,
        "focus": False,
        "tags": tags,
        "priority": priority,
        "parent": None,
        "children": [],
        "chain": None,
        "created": datetime.now().isoformat(timespec="seconds"),
        "completed": None,
    }
    save_state(state)
    type_icon = "⚔️" if qtype == "main" else "🌙"
    tag_str = f" [{', '.join(tags)}]" if tags else ""
    prio_str = f" ▲HIGH" if priority == "high" else ""
    print(f"{type_icon}  Quest {colored(qid, C_CYAN)} added: {args.desc} [{colored(f'+{xp} XP', C_GREEN)}]{prio_str}{tag_str}")


def cmd_sub(args: argparse.Namespace) -> None:
    """Add a sub-quest under an existing parent quest."""
    state = load_state()
    parent_id = args.parent
    # Input validation
    if not args.desc or not args.desc.strip():
        print(colored("❌ Sub-quest description cannot be empty.", C_RED))
        return
    if args.xp is not None and args.xp < 0:
        print(colored("❌ XP must be a positive number.", C_RED))
        return
    if not parent_id.startswith("Q") or not parent_id[1:].replace(".", "").isdigit():
        print(colored(f"❌ Invalid quest ID format: {parent_id}. Expected format: Q1, Q2.1, etc.", C_RED))
        return
    if parent_id not in state["quests"]:
        print(colored(f"Quest {parent_id} not found", C_RED))
        return
    if state["quests"][parent_id]["status"] != "active":
        print(colored(f"Quest {parent_id} already completed", C_RED))
        return
    sid = next_sub_id(state, parent_id)
    xp = args.xp or 10
    # Inherit type from parent
    parent_type = quest_type(state["quests"][parent_id])
    tags = [t.strip() for t in args.tag.split(",")] if args.tag else []
    state["quests"][sid] = {
        "desc": args.desc,
        "xp": xp,
        "status": "active",
        "type": parent_type,
        "focus": False,
        "tags": tags,
        "parent": parent_id,
        "children": [],
        "chain": None,
        "created": datetime.now().isoformat(timespec="seconds"),
        "completed": None,
    }
    state["quests"][parent_id]["children"].append(sid)
    save_state(state)
    print(f"📜 Sub-quest {colored(sid, C_CYAN)} added under {parent_id}: {args.desc} [{colored(f'+{xp} XP', C_GREEN)}]")


def cmd_focus(args: argparse.Namespace) -> None:
    """Mark a quest as focused (max 3 active focuses)."""
    state = load_state()
    qid = args.quest_id
    if not qid.startswith("Q") or not qid[1:].replace(".", "").isdigit():
        print(colored(f"❌ Invalid quest ID format: {qid}. Expected format: Q1, Q2.1, etc.", C_RED))
        return
    if qid not in state["quests"]:
        print(colored(f"Quest {qid} not found", C_RED))
        return
    quest = state["quests"][qid]
    if quest["status"] != "active":
        print(colored(f"Quest {qid} is not active", C_RED))
        return
    if quest_focus(quest):
        print(colored(f"Quest {qid} is already focused", C_YELLOW))
        return
    # Limit max 3 focused quests
    focused_count = sum(1 for q in state["quests"].values()
                        if q["status"] == "active" and quest_focus(q))
    if focused_count >= 3:
        print(colored("⚠️  Max 3 focused quests. Unfocus one first.", C_RED))
        return
    quest["focus"] = True
    save_state(state)
    print(f"🔶 {colored(qid, C_CYAN)} is now in focus: {quest['desc']}")


def cmd_unfocus(args: argparse.Namespace) -> None:
    """Remove focus from a quest."""
    state = load_state()
    qid = args.quest_id
    if not qid.startswith("Q") or not qid[1:].replace(".", "").isdigit():
        print(colored(f"❌ Invalid quest ID format: {qid}. Expected format: Q1, Q2.1, etc.", C_RED))
        return
    if qid not in state["quests"]:
        print(colored(f"Quest {qid} not found", C_RED))
        return
    quest = state["quests"][qid]
    if not quest_focus(quest):
        print(colored(f"Quest {qid} is not focused", C_YELLOW))
        return
    quest["focus"] = False
    save_state(state)
    print(f"⬜ {colored(qid, C_CYAN)} unfocused: {quest['desc']}")


def cmd_done(args: argparse.Namespace) -> None:
    """Mark a quest as complete, award XP, and check level-up."""
    state = load_state()
    config = load_config()
    qid = args.quest_id
    if not qid.startswith("Q") or not qid[1:].replace(".", "").isdigit():
        print(colored(f"❌ Invalid quest ID format: {qid}. Expected format: Q1, Q2.1, etc.", C_RED))
        return
    if qid not in state["quests"]:
        print(colored(f"Quest {qid} not found", C_RED))
        return
    quest = state["quests"][qid]
    if quest["status"] == "done":
        print(colored(f"Quest {qid} already completed", C_RED))
        return
    # Chain check
    if quest["chain"]:
        chain = state["chains"].get(quest["chain"])
        if chain and chain["quests"][chain["current"]] != qid:
            blocker = chain["quests"][chain["current"]]
            print(colored(f"Quest {qid} is blocked — complete {blocker} first", C_RED))
            return
    # Complete
    quest["status"] = "done"
    quest["completed"] = datetime.now().isoformat(timespec="seconds")
    xp_gained = quest["xp"]
    state["xp"] += xp_gained
    state["last_quest_date"] = date.today().isoformat()
    vprint(f"Quest {qid}: +{xp_gained} XP, total now {state['xp']}")
    print(f"✅ {colored(qid, C_MAGENTA)} complete! {colored(f'+{xp_gained} XP', C_GREEN)}")
    # Advance chain
    if quest["chain"]:
        chain = state["chains"][quest["chain"]]
        chain["current"] += 1
        if chain["current"] >= len(chain["quests"]):
            print(f"🔗 Chain \"{quest['chain']}\" complete!")
    # Auto-complete children when parent is completed directly
    if quest["children"]:
        for child_id in quest["children"]:
            child = state["quests"].get(child_id)
            if child and child["status"] != "done":
                child["status"] = "done"
                child["completed"] = datetime.now().isoformat(timespec="seconds")
                state["xp"] += child["xp"]
                xp_gained += child["xp"]
                child_xp = child["xp"]
                print(f"  ✅ {colored(child_id, C_CYAN)} auto-completed! {colored(f'+{child_xp} XP', C_GREEN)}")
    # Parent auto-complete
    if quest["parent"]:
        parent = state["quests"][quest["parent"]]
        if all(state["quests"][c]["status"] == "done" for c in parent["children"]):
            parent["status"] = "done"
            parent["completed"] = datetime.now().isoformat(timespec="seconds")
            bonus = 5
            state["xp"] += bonus
            xp_gained += bonus
            print(f"🏆 Parent {colored(quest['parent'], C_MAGENTA)} auto-completed! {colored(f'+{bonus} XP bonus', C_GREEN)}")
    check_levelup(state, config)
    xp_display = f"{state['xp']}/{state['xp_next']}" if state["xp_next"] else f"{state['xp']}/∞"
    print(f"   XP: {xp_display}")
    save_state(state)


def quest_tags(quest: dict) -> list[str]:
    """Get quest tags with backward compat — defaults to []."""
    return quest.get("tags", [])


def quest_priority(quest: dict) -> str:
    """Get quest priority with backward compat — defaults to 'med'."""
    return quest.get("priority", "med")


def cmd_quests(args: argparse.Namespace) -> None:
    """List all active quests, grouped by type."""
    state = load_state()
    top = [(k, v) for k, v in state["quests"].items() if v["parent"] is None and v["status"] == "active"]
    if not top:
        print("No active quests. Add one with: adquest quest \"desc\"")
        return

    # Tag filter
    tag_filter = args.tag if hasattr(args, "tag") and args.tag else None
    if tag_filter:
        top = [(k, v) for k, v in top if tag_filter in quest_tags(v)]
        if not top:
            print(colored(f"No active quests with tag '{tag_filter}'", C_DIM))
            return

    # Split by type
    main_quests = [(k, v) for k, v in top if quest_type(v) == "main"]
    side_quests = [(k, v) for k, v in top if quest_type(v) == "side"]

    def render_quest_tree(quests, header, header_icon):
        if not quests:
            return
        if FORMAT == "chat":
            print(f"{header_icon} {header}\n")
            for qid, q in sorted(quests, key=lambda x: x[0]):
                focus_tag = " [FOCUS]" if quest_focus(q) else ""
                icon = "🔶" if quest_focus(q) else "⬜"
                chain_tag = f" [🔗 {q['chain']}]" if q["chain"] else ""
                tags = quest_tags(q)
                tag_str = f" 🏷️{','.join(tags)}" if tags else ""
                prio = quest_priority(q)
                prio_str = " 🔴" if prio == "high" else (" 🟡" if prio == "low" else "")
                print(f"{icon} {qid} — {q['desc']} (+{q['xp']}){prio_str}{focus_tag}{chain_tag}{tag_str}")
                for cid in q["children"]:
                    child = state["quests"].get(cid)
                    if child:
                        ci = "✅" if child["status"] == "done" else "⬜"
                        print(f"  {ci} {cid} — {child['desc']} (+{child['xp']})")
            print()
        else:
            print(colored(f"━━━ {header_icon} {header} ━━━", C_CYAN))
            for qid, q in sorted(quests, key=lambda x: x[0]):
                icon = "🔶" if quest_focus(q) else "⬜"
                chain_name = q["chain"]
                chain_tag = f" {colored(f'[🔗 {chain_name}]', C_YELLOW)}" if chain_name else ""
                focus_tag = f" {colored('[FOCUS]', C_YELLOW)}" if quest_focus(q) else ""
                tags = quest_tags(q)
                tag_str = f" {colored(f'[{', '.join(tags)}]', C_DIM)}" if tags else ""
                prio = quest_priority(q)
                prio_str = f" {colored('▲', C_RED)}" if prio == "high" else (f" {colored('▽', C_DIM)}" if prio == "low" else "")
                qxp = q["xp"]
                print(f"  {icon} {colored(qid, C_CYAN)} — {q['desc']} ({colored(f'+{qxp} XP', C_GREEN)}){prio_str}{focus_tag}{chain_tag}{tag_str}")
                for cid in q["children"]:
                    child = state["quests"].get(cid)
                    if child:
                        ci = "✅" if child["status"] == "done" else "⬜"
                        cxp = child["xp"]
                        print(f"     {ci} {colored(cid, C_DIM)} — {child['desc']} ({colored(f'+{cxp} XP', C_GREEN)})")
            print()

    render_quest_tree(main_quests, "Main Quests", "⚔️")
    render_quest_tree(side_quests, "Side Quests", "🌙")


def cmd_status(args: argparse.Namespace) -> None:
    """Display character status: level, XP, HP, MP, streak."""
    state = load_state()
    streak_emoji = "🔥" * min(state["streak"], 5) if state["streak"] > 0 else "❄️"
    xp_display = f"{state['xp']}/{state['xp_next']}" if state["xp_next"] else f"{state['xp']}/∞"
    # Gather focused quests
    focused = [(k, v) for k, v in state["quests"].items()
               if v["status"] == "active" and quest_focus(v)]
    if FORMAT == "chat":
        print(f"🐺 {state['title']} (Lv.{state['level']})")
        print(f"XP: {xp_display} | HP: {state['hp']}/100 | MP: {state['mp']}/100")
        print(f"{streak_emoji} Day {state['streak']}")
        if focused:
            print(f"🔶 Focus: {', '.join(f'{k} — {v['desc']}' for k, v in focused)}")
    else:
        print()
        print(colored(f"  ⚔️  {state['title']}  (Level {state['level']})", C_BOLD))
        print()
        print(f"  XP:     {bar(state['xp'], state['xp_next'] or 1000)} {xp_display}")
        print(f"  HP:     {bar(state['hp'], 100)} {state['hp']}/100")
        print(f"  MP:     {bar(state['mp'], 100)} {state['mp']}/100")
        print(f"  Streak: {streak_emoji} Day {state['streak']}")
        if state["buffs"]:
            print(f"  Buffs:  {', '.join(state['buffs'])}")
        if focused:
            focus_str = ", ".join(f"{colored(k, C_CYAN)}" for k, v in focused)
            print(f"  Focus:  🔶 {focus_str}")
        print()


def cmd_drain(args: argparse.Namespace) -> None:
    """Deduct HP and/or MP with a reason."""
    state = load_state()
    if args.hp < 0 or args.mp < 0:
        print(colored("❌ HP and MP drain values must be positive.", C_RED))
        return
    if not args.reason or not args.reason.strip():
        print(colored("❌ Please provide a reason for the drain.", C_RED))
        return
    state["hp"] = max(0, state["hp"] - args.hp)
    state["mp"] = max(0, state["mp"] - args.mp)
    save_state(state)
    print(f"💀 Drained: {colored(f'-{args.hp} HP', C_RED)}, {colored(f'-{args.mp} MP', C_RED)} ({args.reason})")
    if state["hp"] < 20:
        print(colored("  ⚠️  HP critically low! Consider resting.", C_RED))
    if state["mp"] < 20:
        print(colored("  ⚠️  MP critically low! Consider resting.", C_RED))


def cmd_rest(args: argparse.Namespace) -> None:
    """Restore HP/MP using a predefined rest activity."""
    state = load_state()
    config = load_config()
    presets = config["rest_presets"]
    if args.activity not in presets:
        available = ", ".join(presets.keys())
        print(colored(f"Unknown activity. Available: {available}", C_RED))
        return
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


def cmd_log(args: argparse.Namespace) -> None:
    """Archive today's completed quests to a log file, or view past logs."""
    from datetime import timedelta

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
    log_file = LOGS_DIR / f"log-{today}.md"
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
    log_file = LOGS_DIR / f"log-{target_date}.md"
    if not log_file.exists():
        if not quiet:
            print(colored(f"No log found for {target_date}.", C_DIM))
        return
    with open(log_file, "r") as f:
        content = f.read().strip()
    print(content)
    if not quiet:
        print()


def cmd_edit(args: argparse.Namespace) -> None:
    """Edit an existing quest's description, XP, type, tags, or priority."""
    state = load_state()
    qid = args.quest_id
    if not qid.startswith("Q") or not qid[1:].replace(".", "").isdigit():
        print(colored(f"❌ Invalid quest ID format: {qid}. Expected format: Q1, Q2.1, etc.", C_RED))
        return
    if args.xp is not None and args.xp < 0:
        print(colored("❌ XP must be a positive number.", C_RED))
        return
    if qid not in state["quests"]:
        print(colored(f"Quest {qid} not found", C_RED))
        return
    quest = state["quests"][qid]
    changes = []
    if args.desc:
        quest["desc"] = args.desc
        changes.append(f"desc → \"{args.desc}\"")
    if args.xp is not None:
        quest["xp"] = args.xp
        changes.append(f"xp → {args.xp}")
    if args.type:
        quest["type"] = args.type
        changes.append(f"type → {args.type}")
        # Also update children type
        for cid in quest.get("children", []):
            if cid in state["quests"]:
                state["quests"][cid]["type"] = args.type
        if quest.get("children"):
            changes.append(f"(children updated to {args.type})")
    if args.tag:
        tags = [t.strip() for t in args.tag.split(",")]
        quest["tags"] = tags
        changes.append(f"tags → [{', '.join(tags)}]")
    if args.priority:
        quest["priority"] = args.priority
        changes.append(f"priority → {args.priority}")
    if not changes:
        print(colored("Nothing to change. Use --desc, --xp, --type, --tag, and/or --priority", C_RED))
        return
    save_state(state)
    print(f"✏️  {colored(qid, C_CYAN)} updated: {', '.join(changes)}")


def cmd_reopen(args: argparse.Namespace) -> None:
    """Reopen a completed quest (reverses XP)."""
    state = load_state()
    config = load_config()
    qid = args.quest_id
    if not qid.startswith("Q") or not qid[1:].replace(".", "").isdigit():
        print(colored(f"❌ Invalid quest ID format: {qid}. Expected format: Q1, Q2.1, etc.", C_RED))
        return
    # Check active quests first
    if qid in state["quests"]:
        quest = state["quests"][qid]
        if quest["status"] != "done":
            print(colored(f"Quest {qid} is already active", C_RED))
            return
        # Reverse XP
        xp_lost = quest["xp"]
        state["xp"] = max(0, state["xp"] - xp_lost)
        quest["status"] = "active"
        quest["completed"] = None
        # If parent was auto-completed, reopen it too
        if quest["parent"] and quest["parent"] in state["quests"]:
            parent = state["quests"][quest["parent"]]
            if parent["status"] == "done":
                state["xp"] = max(0, state["xp"] - 5)  # reverse the auto-complete bonus
                parent["status"] = "active"
                parent["completed"] = None
                print(f"↩️  Parent {colored(quest['parent'], C_CYAN)} also reopened (auto-complete reversed)")
        save_state(state)
        print(f"↩️  {colored(qid, C_CYAN)} reopened. {colored(f'-{xp_lost} XP', C_RED)}")
        return
    # Check history
    hist_match = next((i for i, h in enumerate(state["history"]) if h["id"] == qid), None)
    if hist_match is not None:
        entry = state["history"].pop(hist_match)
        xp_lost = entry["xp"]
        state["xp"] = max(0, state["xp"] - xp_lost)
        entry.pop("id")
        entry["status"] = "active"
        entry["completed"] = None
        state["quests"][qid] = entry
        save_state(state)
        print(f"↩️  {colored(qid, C_CYAN)} restored from history. {colored(f'-{xp_lost} XP', C_RED)}")
        return
    print(colored(f"Quest {qid} not found in active quests or history", C_RED))


def cmd_chain(args: argparse.Namespace) -> None:
    """Link quests into a sequential chain."""
    state = load_state()
    name = args.name
    quest_ids = args.quests
    if not name or not name.strip():
        print(colored("❌ Chain name cannot be empty.", C_RED))
        return
    if len(quest_ids) < 2:
        print(colored("❌ A chain needs at least 2 quests.", C_RED))
        return
    for qid in quest_ids:
        if not qid.startswith("Q") or not qid[1:].replace(".", "").isdigit():
            print(colored(f"❌ Invalid quest ID format: {qid}. Expected format: Q1, Q2.1, etc.", C_RED))
            return
        if qid not in state["quests"]:
            print(colored(f"Quest {qid} not found", C_RED))
            return
    state["chains"][name] = {"name": name, "quests": quest_ids, "current": 0}
    for qid in quest_ids:
        state["quests"][qid]["chain"] = name
    save_state(state)
    chain_str = " → ".join(quest_ids)
    print(f"🔗 Chain \"{colored(name, C_YELLOW)}\": {chain_str}")


def cmd_drop(args: argparse.Namespace) -> None:
    """Drop/abandon a quest without awarding XP. Archives with reason."""
    state = load_state()
    qid = args.quest_id
    if not qid.startswith("Q") or not qid[1:].replace(".", "").isdigit():
        print(colored(f"❌ Invalid quest ID format: {qid}. Expected format: Q1, Q2.1, etc.", C_RED))
        return
    if qid not in state["quests"]:
        print(colored(f"Quest {qid} not found", C_RED))
        return
    quest = state["quests"][qid]
    if quest["status"] == "done":
        print(colored(f"Quest {qid} is already completed. Use 'reopen' first if you want to drop it.", C_RED))
        return
    reason = args.reason or "No reason given"
    # Drop the quest
    quest["status"] = "dropped"
    quest["completed"] = datetime.now().isoformat(timespec="seconds")
    quest["drop_reason"] = reason
    # Also drop active children
    dropped_children = []
    for cid in quest.get("children", []):
        child = state["quests"].get(cid)
        if child and child["status"] == "active":
            child["status"] = "dropped"
            child["completed"] = datetime.now().isoformat(timespec="seconds")
            child["drop_reason"] = reason
            dropped_children.append(cid)
    # Remove from chain if applicable
    if quest.get("chain"):
        chain_name = quest["chain"]
        chain = state["chains"].get(chain_name)
        if chain:
            chain["quests"] = [q for q in chain["quests"] if q != qid]
            if not chain["quests"]:
                del state["chains"][chain_name]
    # Move to history
    state["history"].append({"id": qid, **state["quests"].pop(qid)})
    for cid in dropped_children:
        state["history"].append({"id": cid, **state["quests"].pop(cid)})
    state["history"] = state["history"][-50:]
    save_state(state)
    print(f"🗑️  {colored(qid, C_RED)} dropped: {quest['desc']}")
    print(f"   Reason: {reason}")
    if dropped_children:
        print(f"   Also dropped: {', '.join(dropped_children)}")
    print(colored("   No XP awarded. Quest archived.", C_DIM))


def cmd_idle(args: argparse.Namespace) -> None:
    """Show quests that have been idle for N+ days."""
    state = load_state()
    days = args.days or 3
    today = date.today()
    idle_quests = []
    for qid, q in state["quests"].items():
        if q["status"] != "active":
            continue
        created = date.fromisoformat(q["created"][:10])
        age = (today - created).days
        if age >= days:
            idle_quests.append((qid, q, age))
    if not idle_quests:
        print(colored(f"No quests idle for {days}+ days. All fresh!", C_GREEN))
        return
    idle_quests.sort(key=lambda x: x[2], reverse=True)
    print(colored(f"━━━ 💤 Idle Quests ({days}+ days) ━━━", C_YELLOW))
    for qid, q, age in idle_quests:
        if q["parent"]:
            continue  # Only show top-level
        prio = quest_priority(q)
        prio_str = f" {colored('▲', C_RED)}" if prio == "high" else ""
        print(f"  ⬜ {colored(qid, C_CYAN)} — {q['desc']} ({colored(f'{age}d old', C_YELLOW)}){prio_str}")
    print()
    print(colored(f"  {len(idle_quests)} quest(s) growing cold. Move or abandon?", C_DIM))


def cmd_today(args: argparse.Namespace) -> None:
    """Show focused quests and quests created today."""
    state = load_state()
    today = date.today().isoformat()
    # Focused quests
    focused = [(k, v) for k, v in state["quests"].items()
               if v["status"] == "active" and quest_focus(v)]
    # Created today
    created_today = [(k, v) for k, v in state["quests"].items()
                     if v["status"] == "active" and v["created"][:10] == today and not quest_focus(v)]
    if not focused and not created_today:
        print(colored("No focused quests and nothing created today.", C_DIM))
        print("Use: adquest focus Q{id} to set your focus.")
        return
    if focused:
        print(colored("━━━ 🔶 Today's Focus ━━━", C_YELLOW))
        for qid, q in focused:
            qxp = q["xp"]
            print(f"  🔶 {colored(qid, C_CYAN)} — {q['desc']} ({colored(f'+{qxp} XP', C_GREEN)})")
            for cid in q.get("children", []):
                child = state["quests"].get(cid)
                if child and child["status"] == "active":
                    print(f"     ⬜ {colored(cid, C_DIM)} — {child['desc']} ({colored(f'+{child['xp']} XP', C_GREEN)})")
        print()
    if created_today:
        print(colored("━━━ 📋 Added Today ━━━", C_CYAN))
        for qid, q in created_today:
            if q["parent"]:
                continue
            qxp = q["xp"]
            print(f"  ⬜ {colored(qid, C_CYAN)} — {q['desc']} ({colored(f'+{qxp} XP', C_GREEN)})")
        print()


def cmd_summary(args: argparse.Namespace) -> None:
    """Show a daily summary: completed, dropped, added, XP earned, focus status."""
    state = load_state()
    today = date.today().isoformat()
    # Completed today (still in quests dict)
    completed_today = [(k, v) for k, v in state["quests"].items()
                       if v["status"] == "done" and v.get("completed", "")[:10] == today]
    # Also check history (already logged)
    completed_history = [(h["id"], h) for h in state.get("history", [])
                         if h.get("completed", "")[:10] == today and h.get("status") == "done"]
    # Dropped today
    dropped_today = [(h["id"], h) for h in state.get("history", [])
                     if h.get("completed", "")[:10] == today and h.get("status") == "dropped"]
    # Created today (active)
    created_today = [(k, v) for k, v in state["quests"].items()
                     if v["status"] == "active" and v.get("created", "")[:10] == today]
    # Focused quests
    focused = [(k, v) for k, v in state["quests"].items()
               if v["status"] == "active" and quest_focus(v)]
    # XP earned today
    xp_earned = sum(q["xp"] for _, q in completed_today + completed_history)
    # Remaining active
    active_count = sum(1 for v in state["quests"].values() if v["status"] == "active")

    if FORMAT == "chat":
        print(f"📊 Daily Summary — {today}")
        print(f"XP earned: +{xp_earned} | Active quests: {active_count}")
        if completed_today or completed_history:
            print(f"\n✅ Completed ({len(completed_today) + len(completed_history)}):")
            for qid, q in completed_today + completed_history:
                print(f"  - {qid} — {q['desc']} (+{q['xp']})")
        if dropped_today:
            print(f"\n🗑️ Dropped ({len(dropped_today)}):")
            for qid, q in dropped_today:
                reason = q.get("drop_reason", "")
                print(f"  - {qid} — {q['desc']} ({reason})")
        if created_today:
            print(f"\n📋 Added ({len(created_today)}):")
            for qid, q in created_today:
                print(f"  - {qid} — {q['desc']} (+{q['xp']})")
        if focused:
            print(f"\n🔶 Focus:")
            for qid, q in focused:
                print(f"  - {qid} — {q['desc']}")
        if not (completed_today or completed_history or dropped_today or created_today):
            print("\nNothing happened today yet. Time to hunt!")
    else:
        print()
        print(colored(f"  📊 Daily Summary — {today}", C_BOLD))
        print()
        print(f"  XP earned: {colored(f'+{xp_earned}', C_GREEN)} | Active: {active_count} quest(s)")
        if completed_today or completed_history:
            print()
            print(colored(f"  ✅ Completed ({len(completed_today) + len(completed_history)})", C_GREEN))
            for qid, q in completed_today + completed_history:
                print(f"     {colored(qid, C_MAGENTA)} — {q['desc']} ({colored(f'+{q['xp']} XP', C_GREEN)})")
        if dropped_today:
            print()
            print(colored(f"  🗑️  Dropped ({len(dropped_today)})", C_RED))
            for qid, q in dropped_today:
                reason = q.get("drop_reason", "")
                print(f"     {colored(qid, C_DIM)} — {q['desc']} ({reason})")
        if created_today:
            print()
            print(colored(f"  📋 Added ({len(created_today)})", C_CYAN))
            for qid, q in created_today:
                print(f"     {colored(qid, C_CYAN)} — {q['desc']} ({colored(f'+{q['xp']} XP', C_GREEN)})")
        if focused:
            print()
            print(colored("  🔶 Focus", C_YELLOW))
            for qid, q in focused:
                print(f"     {colored(qid, C_CYAN)} — {q['desc']}")
        if not (completed_today or completed_history or dropped_today or created_today):
            print()
            print(colored("  Nothing happened today yet. Time to hunt!", C_DIM))
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
        log_file = LOGS_DIR / f"log-{log_date}.md"
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


def cmd_newday(args: argparse.Namespace) -> None:
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


# --- CLI ---
def main() -> None:
    """CLI entry point — parse arguments and dispatch to command handlers."""
    global FORMAT, VERBOSE
    parser = argparse.ArgumentParser(prog="adquest", description="⚔️ Gamified task management RPG")
    parser.add_argument("--format", choices=["ansi", "chat"], default="ansi", help="Output format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show debug output")
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

    args = parser.parse_args()
    FORMAT = args.format
    VERBOSE = args.verbose
    if not args.command:
        parser.print_help()
        return

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


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        sys.exit(0)
    except Exception as e:
        print(f"\033[31m❌ Unexpected error: {e}\033[0m", file=sys.stderr)
        sys.exit(1)
