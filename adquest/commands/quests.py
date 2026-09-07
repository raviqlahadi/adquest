"""Command handlers: quest lifecycle (add, complete, edit, drop, reopen, chain, focus)."""
from datetime import date, datetime

from ..core.config import load_config
from ..core.model import next_quest_id, next_sub_id, quest_focus, quest_type, validate_qid
from ..core.progression import check_levelup
from ..core.state import load_state, save_state
from ..errors import QuestError
from ..render import colored, vprint, xp_display
from ..render import C_CYAN, C_DIM, C_GREEN, C_MAGENTA, C_RED, C_YELLOW


def cmd_quest(args) -> None:
    """Add a new top-level quest."""
    state = load_state()
    # Input validation
    if not args.desc or not args.desc.strip():
        raise QuestError(colored("❌ Quest description cannot be empty.", C_RED))
    if args.xp is not None and args.xp < 0:
        raise QuestError(colored("❌ XP must be a positive number.", C_RED))
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


def cmd_sub(args) -> None:
    """Add a sub-quest under an existing parent quest."""
    state = load_state()
    parent_id = args.parent
    # Input validation
    if not args.desc or not args.desc.strip():
        raise QuestError(colored("❌ Sub-quest description cannot be empty.", C_RED))
    if args.xp is not None and args.xp < 0:
        raise QuestError(colored("❌ XP must be a positive number.", C_RED))
    validate_qid(parent_id)
    if parent_id not in state["quests"]:
        raise QuestError(colored(f"Quest {parent_id} not found", C_RED))
    if state["quests"][parent_id]["status"] != "active":
        raise QuestError(colored(f"Quest {parent_id} already completed", C_RED))
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


def cmd_focus(args) -> None:
    """Mark a quest as focused (max 3 active focuses)."""
    state = load_state()
    qid = args.quest_id
    validate_qid(qid)
    if qid not in state["quests"]:
        raise QuestError(colored(f"Quest {qid} not found", C_RED))
    quest = state["quests"][qid]
    if quest["status"] != "active":
        raise QuestError(colored(f"Quest {qid} is not active", C_RED))
    if quest_focus(quest):
        raise QuestError(colored(f"Quest {qid} is already focused", C_YELLOW))
    # Limit max 3 focused quests
    focused_count = sum(1 for q in state["quests"].values()
                        if q["status"] == "active" and quest_focus(q))
    if focused_count >= 3:
        raise QuestError(colored("⚠️  Max 3 focused quests. Unfocus one first.", C_RED))
    quest["focus"] = True
    save_state(state)
    print(f"🔶 {colored(qid, C_CYAN)} is now in focus: {quest['desc']}")


def cmd_unfocus(args) -> None:
    """Remove focus from a quest."""
    state = load_state()
    qid = args.quest_id
    validate_qid(qid)
    if qid not in state["quests"]:
        raise QuestError(colored(f"Quest {qid} not found", C_RED))
    quest = state["quests"][qid]
    if not quest_focus(quest):
        raise QuestError(colored(f"Quest {qid} is not focused", C_YELLOW))
    quest["focus"] = False
    save_state(state)
    print(f"⬜ {colored(qid, C_CYAN)} unfocused: {quest['desc']}")


def cmd_done(args) -> None:
    """Mark a quest as complete, award XP, and check level-up."""
    state = load_state()
    config = load_config()
    qid = args.quest_id
    validate_qid(qid)
    if qid not in state["quests"]:
        raise QuestError(colored(f"Quest {qid} not found", C_RED))
    quest = state["quests"][qid]
    if quest["status"] == "done":
        raise QuestError(colored(f"Quest {qid} already completed", C_RED))
    # Chain check
    if quest["chain"]:
        chain = state["chains"].get(quest["chain"])
        if chain and chain["quests"][chain["current"]] != qid:
            blocker = chain["quests"][chain["current"]]
            raise QuestError(colored(f"Quest {qid} is blocked — complete {blocker} first", C_RED))
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
        # Missing children were archived (already done) — treat as complete
        if all(state["quests"].get(c, {"status": "done"})["status"] == "done" for c in parent["children"]):
            parent["status"] = "done"
            parent["completed"] = datetime.now().isoformat(timespec="seconds")
            bonus = 5
            state["xp"] += bonus
            xp_gained += bonus
            print(f"🏆 Parent {colored(quest['parent'], C_MAGENTA)} auto-completed! {colored(f'+{bonus} XP bonus', C_GREEN)}")
    check_levelup(state, config)
    print(f"   XP: {xp_display(state)}")
    save_state(state)


def cmd_edit(args) -> None:
    """Edit an existing quest's description, XP, type, tags, or priority."""
    state = load_state()
    qid = args.quest_id
    validate_qid(qid)
    if args.xp is not None and args.xp < 0:
        raise QuestError(colored("❌ XP must be a positive number.", C_RED))
    if qid not in state["quests"]:
        raise QuestError(colored(f"Quest {qid} not found", C_RED))
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
        raise QuestError(colored("Nothing to change. Use --desc, --xp, --type, --tag, and/or --priority", C_RED))
    save_state(state)
    print(f"✏️  {colored(qid, C_CYAN)} updated: {', '.join(changes)}")


def cmd_reopen(args) -> None:
    """Reopen a completed quest (reverses XP)."""
    state = load_state()
    qid = args.quest_id
    validate_qid(qid)
    # Check active quests first
    if qid in state["quests"]:
        quest = state["quests"][qid]
        if quest["status"] != "done":
            raise QuestError(colored(f"Quest {qid} is already active", C_RED))
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
    raise QuestError(colored(f"Quest {qid} not found in active quests or history", C_RED))


def cmd_chain(args) -> None:
    """Link quests into a sequential chain."""
    state = load_state()
    name = args.name
    quest_ids = args.quests
    if not name or not name.strip():
        raise QuestError(colored("❌ Chain name cannot be empty.", C_RED))
    if len(quest_ids) < 2:
        raise QuestError(colored("❌ A chain needs at least 2 quests.", C_RED))
    for qid in quest_ids:
        validate_qid(qid)
        if qid not in state["quests"]:
            raise QuestError(colored(f"Quest {qid} not found", C_RED))
    state["chains"][name] = {"name": name, "quests": quest_ids, "current": 0}
    for qid in quest_ids:
        state["quests"][qid]["chain"] = name
    save_state(state)
    chain_str = " → ".join(quest_ids)
    print(f"🔗 Chain \"{colored(name, C_YELLOW)}\": {chain_str}")


def cmd_drop(args) -> None:
    """Drop/abandon a quest without awarding XP. Archives with reason."""
    state = load_state()
    qid = args.quest_id
    validate_qid(qid)
    if qid not in state["quests"]:
        raise QuestError(colored(f"Quest {qid} not found", C_RED))
    quest = state["quests"][qid]
    if quest["status"] == "done":
        raise QuestError(colored(f"Quest {qid} is already completed. Use 'reopen' first if you want to drop it.", C_RED))
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
