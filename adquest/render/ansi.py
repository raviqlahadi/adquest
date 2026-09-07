"""ANSI renderer — colored terminal output (v1 look, verbatim)."""
from . import bar, colored
from . import C_BOLD, C_CYAN, C_DIM, C_GREEN, C_MAGENTA, C_RED, C_YELLOW
from . import streak_emoji, xp_display
from .base import Renderer
from ..core.model import quest_focus, quest_priority, quest_tags


class AnsiRenderer(Renderer):
    def quest_tree(self, main_quests: list, side_quests: list, quests_by_id: dict) -> None:
        sections = (
            (main_quests, "Main Quests", "⚔️"),
            (side_quests, "Side Quests", "🌙"),
        )
        for quests, header, header_icon in sections:
            if not quests:
                continue
            print(colored(f"━━━ {header_icon} {header} ━━━", C_CYAN))
            for qid, q in sorted(quests, key=lambda x: x[0]):
                icon = "🔶" if quest_focus(q) else "⬜"
                chain_name = q["chain"]
                chain_tag = f" {colored(f'[🔗 {chain_name}]', C_YELLOW)}" if chain_name else ""
                focus_tag = f" {colored('[FOCUS]', C_YELLOW)}" if quest_focus(q) else ""
                tags = quest_tags(q)
                tag_str = f" {colored('[' + ', '.join(tags) + ']', C_DIM)}" if tags else ""
                prio = quest_priority(q)
                prio_str = f" {colored('▲', C_RED)}" if prio == "high" else (f" {colored('▽', C_DIM)}" if prio == "low" else "")
                qxp = q["xp"]
                print(f"  {icon} {colored(qid, C_CYAN)} — {q['desc']} ({colored(f'+{qxp} XP', C_GREEN)}){prio_str}{focus_tag}{chain_tag}{tag_str}")
                for cid in q["children"]:
                    child = quests_by_id.get(cid)
                    if child:
                        ci = "✅" if child["status"] == "done" else "⬜"
                        cxp = child["xp"]
                        print(f"     {ci} {colored(cid, C_DIM)} — {child['desc']} ({colored(f'+{cxp} XP', C_GREEN)})")
            print()

    def status(self, state: dict, focused: list) -> None:
        print()
        print(colored(f"  ⚔️  {state['title']}  (Level {state['level']})", C_BOLD))
        print()
        print(f"  XP:     {bar(state['xp'], state['xp_next'] or 1000)} {xp_display(state)}")
        print(f"  HP:     {bar(state['hp'], 100)} {state['hp']}/100")
        print(f"  MP:     {bar(state['mp'], 100)} {state['mp']}/100")
        print(f"  Streak: {streak_emoji(state)} Day {state['streak']}")
        if state["buffs"]:
            print(f"  Buffs:  {', '.join(state['buffs'])}")
        if focused:
            focus_str = ", ".join(f"{colored(k, C_CYAN)}" for k, v in focused)
            print(f"  Focus:  🔶 {focus_str}")
        print()

    def summary(self, data: dict) -> None:
        completed = data["completed"]
        dropped = data["dropped"]
        created = data["created"]
        focused = data["focused"]
        print()
        print(colored(f"  📊 Daily Summary — {data['today']}", C_BOLD))
        print()
        xp_earned_str = colored(f"+{data['xp_earned']}", C_GREEN)
        print(f"  XP earned: {xp_earned_str} | Active: {data['active_count']} quest(s)")
        if completed:
            print()
            print(colored(f"  ✅ Completed ({len(completed)})", C_GREEN))
            for qid, q in completed:
                xp_str = colored(f"+{q['xp']} XP", C_GREEN)
                print(f"     {colored(qid, C_MAGENTA)} — {q['desc']} ({xp_str})")
        if dropped:
            print()
            print(colored(f"  🗑️  Dropped ({len(dropped)})", C_RED))
            for qid, q in dropped:
                reason = q.get("drop_reason", "")
                print(f"     {colored(qid, C_DIM)} — {q['desc']} ({reason})")
        if created:
            print()
            print(colored(f"  📋 Added ({len(created)})", C_CYAN))
            for qid, q in created:
                xp_str = colored(f"+{q['xp']} XP", C_GREEN)
                print(f"     {colored(qid, C_CYAN)} — {q['desc']} ({xp_str})")
        if focused:
            print()
            print(colored("  🔶 Focus", C_YELLOW))
            for qid, q in focused:
                print(f"     {colored(qid, C_CYAN)} — {q['desc']}")
        if not (completed or dropped or created):
            print()
            print(colored("  Nothing happened today yet. Time to hunt!", C_DIM))
        print()
