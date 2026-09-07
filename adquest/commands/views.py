"""Read-only command handlers: quests, today, idle, summary."""
from datetime import date

from ..core.model import quest_focus, quest_priority, quest_type
from ..render import colored, get_renderer, C_CYAN, C_DIM, C_GREEN, C_YELLOW
from .. import store as store_mod


def cmd_quests(args) -> None:
    """List all active quests, grouped by type."""
    with store_mod.open_store() as store:
        top = [(qid, q) for qid, q in store.list_quests(status="active") if q["parent"] is None]
        if not top:
            print("No active quests. Add one with: adquest quest \"desc\"")
            return

        # Tag filter
        tag_filter = args.tag if hasattr(args, "tag") and args.tag else None
        if tag_filter:
            from ..core.model import quest_tags
            top = [(qid, q) for qid, q in top if tag_filter in quest_tags(q)]
            if not top:
                print(colored(f"No active quests with tag '{tag_filter}'", C_DIM))
                return

        # Split by type
        main_quests = [(qid, q) for qid, q in top if quest_type(q) == "main"]
        side_quests = [(qid, q) for qid, q in top if quest_type(q) == "side"]

        # Renderer resolves children through this lookup (all statuses, v1 parity)
        quests_by_id = dict(store.list_quests())

    get_renderer().quest_tree(main_quests, side_quests, quests_by_id)


def cmd_idle(args) -> None:
    """Show quests that have been idle for N+ days."""
    days = args.days or 3
    today = date.today()
    with store_mod.open_store() as store:
        idle_quests = []
        for qid, q in store.list_quests(status="active"):
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
    today = date.today().isoformat()
    with store_mod.open_store() as store:
        active = store.list_quests(status="active")
        # Focused quests
        focused = [(qid, q) for qid, q in active if quest_focus(q)]
        # Created today
        created_today = [(qid, q) for qid, q in active
                         if q["created"][:10] == today and not quest_focus(q)]
        if not focused and not created_today:
            print(colored("No focused quests and nothing created today.", C_DIM))
            print("Use: adquest focus Q{id} to set your focus.")
            return
        quests_by_id = dict(store.list_quests())
    if focused:
        print(colored("━━━ 🔶 Today's Focus ━━━", C_YELLOW))
        for qid, q in focused:
            qxp = q["xp"]
            print(f"  🔶 {colored(qid, C_CYAN)} — {q['desc']} ({colored(f'+{qxp} XP', C_GREEN)})")
            for cid in q.get("children", []):
                child = quests_by_id.get(cid)
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
    today = date.today().isoformat()
    with store_mod.open_store() as store:
        # Completed today (still in quests dict)
        completed_today = [(qid, q) for qid, q in store.list_quests(status="done")
                           if q.get("completed", "")[:10] == today]
        # Also check history (already logged)
        history = store.get_history()
        completed_history = [(qid, h) for qid, h in history
                             if h.get("completed", "")[:10] == today and h.get("status") == "done"]
        # Dropped today
        dropped_today = [(qid, h) for qid, h in history
                         if h.get("completed", "")[:10] == today and h.get("status") == "dropped"]
        # Created today (active)
        created_today = [(qid, q) for qid, q in store.list_quests(status="active")
                         if q.get("created", "")[:10] == today]
        # Focused quests
        focused = [(qid, q) for qid, q in store.list_quests(status="active") if quest_focus(q)]
        # Remaining active
        active_count = len(store.list_quests(status="active"))

    completed = completed_today + completed_history
    # XP earned today
    xp_earned = sum(q["xp"] for _, q in completed)

    data = {
        "today": today,
        "completed": completed,
        "dropped": dropped_today,
        "created": created_today,
        "focused": focused,
        "xp_earned": xp_earned,
        "active_count": active_count,
    }
    get_renderer().summary(data)
