"""XP awarding and level-up mechanics."""
from ..render import colored, C_YELLOW


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
