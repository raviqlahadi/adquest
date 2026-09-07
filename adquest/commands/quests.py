"""Command handlers: quest lifecycle (add, complete, edit, drop, reopen, chain, focus)."""
from datetime import date, datetime

from ..core.config import load_config
from ..core.model import next_quest_id, next_sub_id, quest_focus, quest_type, validate_qid
from ..core.progression import check_levelup
from ..errors import QuestError
from ..render import colored, vprint, xp_display
from ..render import C_CYAN, C_DIM, C_GREEN, C_MAGENTA, C_RED, C_YELLOW
from .. import store as store_mod


def cmd_quest(args) -> None:
    """Add a new top-level quest."""
    # Input validation
    if not args.desc or not args.desc.strip():
        raise QuestError(colored("❌ Quest description cannot be empty.", C_RED))
    if args.xp is not None and args.xp < 0:
        raise QuestError(colored("❌ XP must be a positive number.", C_RED))
    with store_mod.open_store() as store:
        qid = next_quest_id(store)
        xp = args.xp or 10
        qtype = args.type or "main"
        tags = [t.strip() for t in args.tag.split(",")] if args.tag else []
        priority = args.priority or "med"
        store.add_quest(qid, {
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
        })
        store.commit()
    type_icon = "⚔️" if qtype == "main" else "🌙"
    tag_str = f" [{', '.join(tags)}]" if tags else ""
    prio_str = f" ▲HIGH" if priority == "high" else ""
    print(f"{type_icon}  Quest {colored(qid, C_CYAN)} added: {args.desc} [{colored(f'+{xp} XP', C_GREEN)}]{prio_str}{tag_str}")


def cmd_sub(args) -> None:
    """Add a sub-quest under an existing parent quest."""
    parent_id = args.parent
    # Input validation
    if not args.desc or not args.desc.strip():
        raise QuestError(colored("❌ Sub-quest description cannot be empty.", C_RED))
    if args.xp is not None and args.xp < 0:
        raise QuestError(colored("❌ XP must be a positive number.", C_RED))
    validate_qid(parent_id)
    with store_mod.open_store() as store:
        parent = store.get_quest(parent_id)
        if parent is None:
            raise QuestError(colored(f"Quest {parent_id} not found", C_RED))
        if parent["status"] != "active":
            raise QuestError(colored(f"Quest {parent_id} already completed", C_RED))
        sid = next_sub_id(store, parent_id)
        xp = args.xp or 10
        # Inherit type from parent
        parent_type = quest_type(parent)
        tags = [t.strip() for t in args.tag.split(",")] if args.tag else []
        store.add_quest(sid, {
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
        })
        parent["children"].append(sid)
        store.update_quest(parent_id, {"children": parent["children"]})
        store.commit()
    print(f"📜 Sub-quest {colored(sid, C_CYAN)} added under {parent_id}: {args.desc} [{colored(f'+{xp} XP', C_GREEN)}]")


def cmd_focus(args) -> None:
    """Mark a quest as focused (max 3 active focuses)."""
    qid = args.quest_id
    validate_qid(qid)
    with store_mod.open_store() as store:
        quest = store.get_quest(qid)
        if quest is None:
            raise QuestError(colored(f"Quest {qid} not found", C_RED))
        if quest["status"] != "active":
            raise QuestError(colored(f"Quest {qid} is not active", C_RED))
        if quest_focus(quest):
            raise QuestError(colored(f"Quest {qid} is already focused", C_YELLOW))
        # Limit max 3 focused quests
        focused_count = sum(1 for _, q in store.list_quests(status="active") if quest_focus(q))
        if focused_count >= 3:
            raise QuestError(colored("⚠️  Max 3 focused quests. Unfocus one first.", C_RED))
        store.update_quest(qid, {"focus": True})
        store.commit()
    print(f"🔶 {colored(qid, C_CYAN)} is now in focus: {quest['desc']}")


def cmd_unfocus(args) -> None:
    """Remove focus from a quest."""
    qid = args.quest_id
    validate_qid(qid)
    with store_mod.open_store() as store:
        quest = store.get_quest(qid)
        if quest is None:
            raise QuestError(colored(f"Quest {qid} not found", C_RED))
        if not quest_focus(quest):
            raise QuestError(colored(f"Quest {qid} is not focused", C_YELLOW))
        store.update_quest(qid, {"focus": False})
        store.commit()
    print(f"⬜ {colored(qid, C_CYAN)} unfocused: {quest['desc']}")


def cmd_done(args) -> None:
    """Mark a quest as complete, award XP, and check level-up."""
    config = load_config()
    qid = args.quest_id
    validate_qid(qid)
    with store_mod.open_store() as store:
        quest = store.get_quest(qid)
        if quest is None:
            raise QuestError(colored(f"Quest {qid} not found", C_RED))
        if quest["status"] == "done":
            raise QuestError(colored(f"Quest {qid} already completed", C_RED))
        # Chain check
        chain = None
        if quest["chain"]:
            chain = store.get_chain(quest["chain"])
            if chain and chain["quests"][chain["current"]] != qid:
                blocker = chain["quests"][chain["current"]]
                raise QuestError(colored(f"Quest {qid} is blocked — complete {blocker} first", C_RED))
        # Complete
        now = datetime.now().isoformat(timespec="seconds")
        store.update_quest(qid, {"status": "done", "completed": now})
        xp_gained = quest["xp"]
        player = store.get_player()
        player["xp"] += xp_gained
        player["last_quest_date"] = date.today().isoformat()
        vprint(f"Quest {qid}: +{xp_gained} XP, total now {player['xp']}")
        print(f"✅ {colored(qid, C_MAGENTA)} complete! {colored(f'+{xp_gained} XP', C_GREEN)}")
        # Advance chain
        if chain:
            chain["current"] += 1
            store.upsert_chain(quest["chain"], chain)
            if chain["current"] >= len(chain["quests"]):
                print(f"🔗 Chain \"{quest['chain']}\" complete!")
        # Auto-complete children when parent is completed directly
        if quest["children"]:
            for child_id in quest["children"]:
                child = store.get_quest(child_id)
                if child and child["status"] != "done":
                    store.update_quest(child_id, {"status": "done", "completed": now})
                    player["xp"] += child["xp"]
                    xp_gained += child["xp"]
                    child_xp = child["xp"]
                    print(f"  ✅ {colored(child_id, C_CYAN)} auto-completed! {colored(f'+{child_xp} XP', C_GREEN)}")
        # Parent auto-complete
        if quest["parent"]:
            parent = store.get_quest(quest["parent"])
            if parent is not None:
                # Missing children were archived (already done) — treat as complete
                if all((store.get_quest(c) or {"status": "done"})["status"] == "done" for c in parent["children"]):
                    store.update_quest(quest["parent"], {"status": "done", "completed": now})
                    bonus = 5
                    player["xp"] += bonus
                    xp_gained += bonus
                    print(f"🏆 Parent {colored(quest['parent'], C_MAGENTA)} auto-completed! {colored(f'+{bonus} XP bonus', C_GREEN)}")
        check_levelup(player, config)
        store.update_player(player)
        store.commit()
        print(f"   XP: {xp_display(player)}")


def cmd_edit(args) -> None:
    """Edit an existing quest's description, XP, type, tags, or priority."""
    qid = args.quest_id
    validate_qid(qid)
    if args.xp is not None and args.xp < 0:
        raise QuestError(colored("❌ XP must be a positive number.", C_RED))
    with store_mod.open_store() as store:
        quest = store.get_quest(qid)
        if quest is None:
            raise QuestError(colored(f"Quest {qid} not found", C_RED))
        changes = []
        fields = {}
        if args.desc:
            fields["desc"] = args.desc
            changes.append(f"desc → \"{args.desc}\"")
        if args.xp is not None:
            fields["xp"] = args.xp
            changes.append(f"xp → {args.xp}")
        if args.type:
            fields["type"] = args.type
            changes.append(f"type → {args.type}")
            # Also update children type
            for cid in quest.get("children", []):
                if store.get_quest(cid) is not None:
                    store.update_quest(cid, {"type": args.type})
            if quest.get("children"):
                changes.append(f"(children updated to {args.type})")
        if args.tag:
            tags = [t.strip() for t in args.tag.split(",")]
            fields["tags"] = tags
            changes.append(f"tags → [{', '.join(tags)}]")
        if args.priority:
            fields["priority"] = args.priority
            changes.append(f"priority → {args.priority}")
        if not changes:
            raise QuestError(colored("Nothing to change. Use --desc, --xp, --type, --tag, and/or --priority", C_RED))
        store.update_quest(qid, fields)
        store.commit()
    print(f"✏️  {colored(qid, C_CYAN)} updated: {', '.join(changes)}")


def cmd_reopen(args) -> None:
    """Reopen a completed quest (reverses XP)."""
    qid = args.quest_id
    validate_qid(qid)
    with store_mod.open_store() as store:
        quest = store.get_quest(qid)
        if quest is not None:
            if quest["status"] != "done":
                raise QuestError(colored(f"Quest {qid} is already active", C_RED))
            # Reverse XP
            player = store.get_player()
            xp_lost = quest["xp"]
            player["xp"] = max(0, player["xp"] - xp_lost)
            # If parent was auto-completed, reopen it too
            if quest["parent"] and store.get_quest(quest["parent"]) is not None:
                parent = store.get_quest(quest["parent"])
                if parent["status"] == "done":
                    player["xp"] = max(0, player["xp"] - 5)  # reverse the auto-complete bonus
                    store.update_quest(quest["parent"], {"status": "active", "completed": None})
                    print(f"↩️  Parent {colored(quest['parent'], C_CYAN)} also reopened (auto-complete reversed)")
            store.update_quest(qid, {"status": "active", "completed": None})
            store.update_player(player)
            store.commit()
            print(f"↩️  {colored(qid, C_CYAN)} reopened. {colored(f'-{xp_lost} XP', C_RED)}")
            return
        # Check history
        restored = store.restore_from_history(qid)
        if restored is not None:
            # Reactivate — v1 semantics (restore alone keeps status=done)
            store.update_quest(qid, {"status": "active", "completed": None})
            player = store.get_player()
            xp_lost = restored["xp"]
            player["xp"] = max(0, player["xp"] - xp_lost)
            store.update_player(player)
            store.commit()
            print(f"↩️  {colored(qid, C_CYAN)} restored from history. {colored(f'-{xp_lost} XP', C_RED)}")
            return
        raise QuestError(colored(f"Quest {qid} not found in active quests or history", C_RED))


def cmd_chain(args) -> None:
    """Link quests into a sequential chain."""
    name = args.name
    quest_ids = args.quests
    if not name or not name.strip():
        raise QuestError(colored("❌ Chain name cannot be empty.", C_RED))
    if len(quest_ids) < 2:
        raise QuestError(colored("❌ A chain needs at least 2 quests.", C_RED))
    with store_mod.open_store() as store:
        for qid in quest_ids:
            validate_qid(qid)
            if store.get_quest(qid) is None:
                raise QuestError(colored(f"Quest {qid} not found", C_RED))
        store.upsert_chain(name, {"name": name, "quests": quest_ids, "current": 0})
        for qid in quest_ids:
            store.update_quest(qid, {"chain": name})
        store.commit()
    chain_str = " → ".join(quest_ids)
    print(f"🔗 Chain \"{colored(name, C_YELLOW)}\": {chain_str}")


def cmd_drop(args) -> None:
    """Drop/abandon a quest without awarding XP. Archives with reason."""
    qid = args.quest_id
    validate_qid(qid)
    with store_mod.open_store() as store:
        quest = store.get_quest(qid)
        if quest is None:
            raise QuestError(colored(f"Quest {qid} not found", C_RED))
        if quest["status"] == "done":
            raise QuestError(colored(f"Quest {qid} is already completed. Use 'reopen' first if you want to drop it.", C_RED))
        reason = args.reason or "No reason given"
        now = datetime.now().isoformat(timespec="seconds")
        # Drop the quest
        store.update_quest(qid, {"status": "dropped", "completed": now, "drop_reason": reason})
        # Also drop active children
        dropped_children = []
        for cid in quest.get("children", []):
            child = store.get_quest(cid)
            if child and child["status"] == "active":
                store.update_quest(cid, {"status": "dropped", "completed": now, "drop_reason": reason})
                dropped_children.append(cid)
        # Remove from chain if applicable
        if quest.get("chain"):
            chain = store.get_chain(quest["chain"])
            if chain:
                chain["quests"] = [q for q in chain["quests"] if q != qid]
                if not chain["quests"]:
                    store.delete_chain(quest["chain"])
                else:
                    store.upsert_chain(quest["chain"], chain)
        # Move to history
        store.move_to_history(qid)
        for cid in dropped_children:
            store.move_to_history(cid)
        store.commit()
    print(f"🗑️  {colored(qid, C_RED)} dropped: {quest['desc']}")
    print(f"   Reason: {reason}")
    if dropped_children:
        print(f"   Also dropped: {', '.join(dropped_children)}")
    print(colored("   No XP awarded. Quest archived.", C_DIM))
