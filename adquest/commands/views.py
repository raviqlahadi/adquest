"""Read-only command handlers: quests, today, idle, summary."""
from datetime import date

from ..core.model import quest_focus, quest_priority, quest_type, quest_tags
from ..core.state import load_state
from ..render import colored, get_renderer, C_CYAN, C_DIM, C_GREEN, C_YELLOW


def cmd_quests(args) -> None:
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

    get_renderer().quest_tree(main_quests, side_quests, state)


def cmd_idle(args) -> None:
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
    shown = 0
    for qid, q, age in idle_quests:
        if q["parent"]:
            continue  # Only show top-level
        shown += 1
        prio = quest_priority(q)
        prio_str = f" {colored('▲', C_RED)}" if prio == "high" else ""
        print(f"  ⬜ {colored(qid, C_CYAN)} — {q['desc']} ({colored(f'{age}d old', C_YELLOW)}){prio_str}")
    print()
    print(colored(f"  {shown} quest(s) growing cold. Move or abandon?", C_DIM))


def cmd_today(args) -> None:
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


def cmd_summary(args) -> None:
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

    data = {
        "today": today,
        "completed": completed_today + completed_history,
        "dropped": dropped_today,
        "created": created_today,
        "focused": focused,
        "xp_earned": xp_earned,
        "active_count": active_count,
    }
    get_renderer().summary(data)
