"""Quest ID generation, validation, and the quest-field accessors."""
from ..errors import QuestError


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


def validate_qid(qid: str) -> None:
    """Validate quest ID format (Q1, Q2.1, ...). Raises QuestError if invalid."""
    if not qid.startswith("Q") or not qid[1:].replace(".", "").isdigit():
        raise QuestError(
            f"❌ Invalid quest ID format: {qid}. Expected format: Q1, Q2.1, etc."
        )


# --- Quest-field accessors (backward compat with old state files) ---

def quest_type(quest: dict) -> str:
    """Get quest type — defaults to 'main' for pre-types state."""
    return quest.get("type", "main")


def quest_focus(quest: dict) -> bool:
    """Get quest focus — defaults to False for pre-focus state."""
    return quest.get("focus", False)


def quest_tags(quest: dict) -> list[str]:
    """Get quest tags — defaults to [] for pre-tags state."""
    return quest.get("tags", [])


def quest_priority(quest: dict) -> str:
    """Get quest priority — defaults to 'med' for pre-priority state."""
    return quest.get("priority", "med")
