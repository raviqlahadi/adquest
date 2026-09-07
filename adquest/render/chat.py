"""Chat renderer — plain-text output for AI agents (--format chat, v1 look)."""
from . import streak_emoji, xp_display
from .base import Renderer
from ..core.model import quest_focus, quest_priority, quest_tags


class ChatRenderer(Renderer):
    def quest_tree(self, main_quests: list, side_quests: list, state: dict) -> None:
        sections = (
            (main_quests, "Main Quests", "⚔️"),
            (side_quests, "Side Quests", "🌙"),
        )
        for quests, header, header_icon in sections:
            if not quests:
                continue
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

    def status(self, state: dict, focused: list) -> None:
        print(f"🐺 {state['title']} (Lv.{state['level']})")
        print(f"XP: {xp_display(state)} | HP: {state['hp']}/100 | MP: {state['mp']}/100")
        print(f"{streak_emoji(state)} Day {state['streak']}")
        if focused:
            focus_str = ", ".join(f"{k} — {q['desc']}" for k, q in focused)
            print(f"🔶 Focus: {focus_str}")

    def summary(self, data: dict) -> None:
        completed = data["completed"]
        dropped = data["dropped"]
        created = data["created"]
        focused = data["focused"]
        print(f"📊 Daily Summary — {data['today']}")
        print(f"XP earned: +{data['xp_earned']} | Active quests: {data['active_count']}")
        if completed:
            print(f"\n✅ Completed ({len(completed)}):")
            for qid, q in completed:
                print(f"  - {qid} — {q['desc']} (+{q['xp']})")
        if dropped:
            print(f"\n🗑️ Dropped ({len(dropped)}):")
            for qid, q in dropped:
                reason = q.get("drop_reason", "")
                print(f"  - {qid} — {q['desc']} ({reason})")
        if created:
            print(f"\n📋 Added ({len(created)}):")
            for qid, q in created:
                print(f"  - {qid} — {q['desc']} (+{q['xp']})")
        if focused:
            print(f"\n🔶 Focus:")
            for qid, q in focused:
                print(f"  - {qid} — {q['desc']}")
        if not (completed or dropped or created):
            print("\nNothing happened today yet. Time to hunt!")
