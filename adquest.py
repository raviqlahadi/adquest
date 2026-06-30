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


# --- Colors ---
C_RESET = "\033[0m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"


def colored(text, color):
    if FORMAT == "chat":
        return text
    return f"{color}{text}{C_RESET}"


def bar(current, maximum, width=20):
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


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return DEFAULT_CONFIG


def save_config(config):
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")


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


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_state():
    ensure_dirs()
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return DEFAULT_STATE.copy()


def save_state(state):
    ensure_dirs()
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


# --- Level-up ---
def check_levelup(state, config):
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
def next_quest_id(state):
    top_ids = [k for k in state["quests"] if "." not in k]
    if not top_ids:
        return "Q1"
    nums = [int(k[1:]) for k in top_ids]
    return f"Q{max(nums) + 1}"


def next_sub_id(state, parent_id):
    parent = state["quests"].get(parent_id)
    if not parent:
        return None
    return f"{parent_id}.{len(parent['children']) + 1}"


# --- Commands ---
def quest_type(quest):
    """Get quest type with backward compat — defaults to 'main'."""
    return quest.get("type", "main")


def quest_focus(quest):
    """Get quest focus with backward compat — defaults to False."""
    return quest.get("focus", False)


def cmd_quest(args):
    state = load_state()
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


def cmd_sub(args):
    state = load_state()
    parent_id = args.parent
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


def cmd_focus(args):
    state = load_state()
    qid = args.quest_id
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


def cmd_unfocus(args):
    state = load_state()
    qid = args.quest_id
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


def cmd_done(args):
    state = load_state()
    config = load_config()
    qid = args.quest_id
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
    print(f"✅ {colored(qid, C_MAGENTA)} complete! {colored(f'+{xp_gained} XP', C_GREEN)}")
    # Advance chain
    if quest["chain"]:
        chain = state["chains"][quest["chain"]]
        chain["current"] += 1
        if chain["current"] >= len(chain["quests"]):
            print(f"🔗 Chain \"{quest['chain']}\" complete!")
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


def quest_tags(quest):
    """Get quest tags with backward compat — defaults to []."""
    return quest.get("tags", [])


def quest_priority(quest):
    """Get quest priority with backward compat — defaults to 'med'."""
    return quest.get("priority", "med")


def cmd_quests(args):
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


def cmd_status(args):
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


def cmd_drain(args):
    state = load_state()
    state["hp"] = max(0, state["hp"] - args.hp)
    state["mp"] = max(0, state["mp"] - args.mp)
    save_state(state)
    print(f"💀 Drained: {colored(f'-{args.hp} HP', C_RED)}, {colored(f'-{args.mp} MP', C_RED)} ({args.reason})")
    if state["hp"] < 20:
        print(colored("  ⚠️  HP critically low! Consider resting.", C_RED))
    if state["mp"] < 20:
        print(colored("  ⚠️  MP critically low! Consider resting.", C_RED))


def cmd_rest(args):
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


def cmd_log(args):
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
    with open(log_file, "a") as f:
        f.writelines(lines)
    # Move to history, keep last 50
    for qid in done_today:
        state["history"].append({"id": qid, **state["quests"].pop(qid)})
    state["history"] = state["history"][-50:]
    save_state(state)
    print(f"📝 Logged {len(done_today)} quest(s) to {colored(str(log_file), C_DIM)}")


def cmd_edit(args):
    state = load_state()
    qid = args.quest_id
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


def cmd_reopen(args):
    state = load_state()
    config = load_config()
    qid = args.quest_id
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


def cmd_chain(args):
    state = load_state()
    name = args.name
    quest_ids = args.quests
    for qid in quest_ids:
        if qid not in state["quests"]:
            print(colored(f"Quest {qid} not found", C_RED))
            return
    state["chains"][name] = {"name": name, "quests": quest_ids, "current": 0}
    for qid in quest_ids:
        state["quests"][qid]["chain"] = name
    save_state(state)
    chain_str = " → ".join(quest_ids)
    print(f"🔗 Chain \"{colored(name, C_YELLOW)}\": {chain_str}")


def cmd_idle(args):
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


def cmd_today(args):
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


def auto_log_previous_day(state):
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
        with open(log_file, "a") as f:
            f.writelines(lines)
        # Move to history
        for qid in quests:
            state["history"].append({"id": qid, **state["quests"].pop(qid)})

    state["history"] = state["history"][-50:]
    total = sum(len(q) for q in to_log.values())
    dates = ", ".join(sorted(to_log.keys()))
    print(f"📝 Auto-logged {total} quest(s) from {dates}")
    return state


def cmd_newday(args):
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
def main():
    global FORMAT
    parser = argparse.ArgumentParser(prog="adquest", description="⚔️ Gamified task management RPG")
    parser.add_argument("--format", choices=["ansi", "chat"], default="ansi", help="Output format")
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

    sub.add_parser("log", help="Archive completed quests")

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

    args = parser.parse_args()
    FORMAT = args.format
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


if __name__ == "__main__":
    main()
