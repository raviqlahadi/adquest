"""Tests for adquest — core functions and state integrity.

Paths are redirected by patching attributes on ``adquest.paths`` (all
modules read path constants via attribute lookup, so a single patch site
redirects every consumer). Fixtures seed state at the file level; state
is read back through the store API (``FileStore().load()``), which is
byte-compatible with the v1 state.json format.
"""

import argparse
import json
import tempfile
from copy import deepcopy
from datetime import date as d
from pathlib import Path

import pytest

import adquest
import adquest.paths as paths
from adquest.store import DEFAULT_STATE
from adquest.store.file import FileStore

# Override module-level paths for testing (before any command runs).
# Tempdirs live on ext4 (~/.cache) rather than /tmp — tmpfs inode reuse
# can carry orphaned flocks from system daemons into fresh lock files.
_test_root = Path.home() / ".cache" / "adquest-tests"
_test_root.mkdir(parents=True, exist_ok=True)
_test_dir = tempfile.mkdtemp(dir=_test_root)
_test_data_dir = Path(_test_dir) / ".adquest"
_test_state_file = _test_data_dir / "state.json"
_test_config_file = _test_data_dir / "config.json"
_test_logs_dir = _test_data_dir / "logs"

paths.DATA_DIR = _test_data_dir
paths.STATE_FILE = _test_state_file
paths.CONFIG_FILE = _test_config_file
paths.LOGS_DIR = _test_logs_dir

from adquest.core import config as config_mod
from adquest.core.model import (
    next_quest_id,
    next_sub_id,
    quest_focus,
    quest_priority,
    quest_tags,
    quest_type,
    validate_qid,
)
from adquest.render import bar, colored


def _seed_state(blob: dict) -> None:
    """Seed state at the file level (bypasses the store — fixture setup)."""
    paths.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.STATE_FILE.write_text(json.dumps(blob, indent=2))


def _read_state() -> dict:
    """Read the full state blob through the store API."""
    with FileStore() as store:
        return store.load()


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    _test_data_dir.mkdir(parents=True, exist_ok=True)
    _test_logs_dir.mkdir(parents=True, exist_ok=True)
    # Write a clean default state
    _seed_state(DEFAULT_STATE)
    # Write default config
    paths.CONFIG_FILE.write_text(json.dumps(config_mod.DEFAULT_CONFIG, indent=2))
    yield
    # Cleanup
    if _test_state_file.exists():
        _test_state_file.unlink()
    backup = _test_state_file.with_suffix(".json.bak")
    if backup.exists():
        backup.unlink()
    if _test_config_file.exists():
        _test_config_file.unlink()
    lock = _test_data_dir / "state.lock"
    if lock.exists():
        lock.unlink()
    for f in _test_logs_dir.glob("*"):
        f.unlink()


# --- Store lifecycle tests ---

class TestStoreLifecycle:
    def test_lock_prevents_concurrent_open(self):
        store = FileStore()
        try:
            with pytest.raises(adquest.QuestError, match="lock"):
                FileStore()
        finally:
            store.close()
        # Releasable after close
        second = FileStore()
        second.close()

    def test_context_manager_releases_lock(self):
        with FileStore() as store:
            assert store.get_player()["level"] == 1
        FileStore().close()  # must not raise

    def test_commit_persists_and_no_commit_discards(self):
        with FileStore() as store:
            store.add_quest("Q1", {"desc": "Committed", "xp": 5, "status": "active",
                                   "parent": None, "children": []})
            store.commit()
        assert _read_state()["quests"]["Q1"]["desc"] == "Committed"

        with FileStore() as store:
            store.add_quest("Q2", {"desc": "Discarded", "xp": 5, "status": "active",
                                   "parent": None, "children": []})
            # no commit — closes without persisting
        assert "Q2" not in _read_state()["quests"]

    def test_copy_on_read_contract(self):
        with FileStore() as store:
            store.add_quest("Q1", {"desc": "Original", "xp": 5, "status": "active",
                                   "parent": None, "children": []})
            store.commit()
        with FileStore() as store:
            quest = store.get_quest("Q1")
            quest["desc"] = "Mutated copy"  # must NOT affect stored state
        assert _read_state()["quests"]["Q1"]["desc"] == "Original"

    def test_query_helpers(self):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"]["Q1"] = {
            "desc": "Done tagged", "xp": 5, "status": "done", "type": "main",
            "tags": ["work"], "parent": None, "children": [], "chain": None,
            "created": "2026-09-01T10:00:00", "completed": "2026-09-05T12:00:00",
        }
        blob["history"].append({"id": "Q2", "desc": "Hist done", "xp": 5, "status": "done",
                                "tags": ["work"], "parent": None, "children": [],
                                "completed": "2026-09-06T12:00:00"})
        blob["history"].append({"id": "Q3", "desc": "Hist dropped", "xp": 5, "status": "dropped",
                                "tags": [], "parent": None, "children": [],
                                "completed": "2026-09-06T12:00:00"})
        _seed_state(blob)
        with FileStore() as store:
            assert store.count_completed() == 2
            assert store.count_completed(tag="work") == 2
            assert store.count_completed(tag="nope") == 0
            between = store.completed_between("2026-09-05", "2026-09-06")
            assert {qid for qid, _ in between} == {"Q1", "Q2"}
            assert {qid for qid, _ in store.completed_between("2026-09-05", "2026-09-05")} == {"Q1"}
            assert store.all_quest_ids() == ["Q1", "Q2", "Q3"]

    def test_move_and_restore_history(self):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"]["Q1"] = {
            "desc": "To archive", "xp": 5, "status": "done", "type": "main",
            "tags": [], "parent": None, "children": [], "chain": None,
            "created": "2026-09-01T10:00:00", "completed": "2026-09-05T12:00:00",
        }
        _seed_state(blob)
        with FileStore() as store:
            store.move_to_history("Q1")
            assert store.get_quest("Q1") is None
            assert [qid for qid, _ in store.get_history()] == ["Q1"]
            restored = store.restore_from_history("Q1")
            assert restored["desc"] == "To archive"
            assert store.get_quest("Q1")["desc"] == "To archive"
            assert store.get_history() == []
            assert store.restore_from_history("Q999") is None
            store.commit()
        assert "Q1" in _read_state()["quests"]


# --- next_quest_id tests ---

class TestNextQuestId:
    def test_empty_state_returns_q1(self):
        with FileStore() as store:
            assert next_quest_id(store) == "Q1"

    def test_increments_from_existing(self):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"] = {"Q1": {}, "Q3": {}}
        _seed_state(blob)
        with FileStore() as store:
            assert next_quest_id(store) == "Q4"

    def test_skips_sub_quests(self):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"] = {"Q1": {}, "Q1.1": {}, "Q1.2": {}}
        _seed_state(blob)
        with FileStore() as store:
            assert next_quest_id(store) == "Q2"

    def test_checks_history_for_collisions(self):
        blob = deepcopy(DEFAULT_STATE)
        blob["history"] = [{"id": "Q5"}, {"id": "Q10"}]
        _seed_state(blob)
        with FileStore() as store:
            assert next_quest_id(store) == "Q11"

    def test_checks_both_active_and_history(self):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"] = {"Q3": {}}
        blob["history"] = [{"id": "Q7"}]
        _seed_state(blob)
        with FileStore() as store:
            assert next_quest_id(store) == "Q8"


# --- next_sub_id tests ---

class TestNextSubId:
    def _seed_parent(self, children):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"]["Q1"] = {"children": children}
        _seed_state(blob)

    def test_first_sub_quest(self):
        self._seed_parent([])
        with FileStore() as store:
            assert next_sub_id(store, "Q1") == "Q1.1"

    def test_increments_sub_quest(self):
        self._seed_parent(["Q1.1", "Q1.2"])
        with FileStore() as store:
            assert next_sub_id(store, "Q1") == "Q1.3"

    def test_invalid_parent_returns_none(self):
        with FileStore() as store:
            assert next_sub_id(store, "Q99") is None


# --- validate_qid tests ---

class TestValidateQid:
    @pytest.mark.parametrize("good", ["Q1", "Q42", "Q1.1", "Q12.3"])
    def test_accepts_valid_formats(self, good):
        validate_qid(good)  # should not raise

    @pytest.mark.parametrize("bad", ["", "Q", "Q-1", "hello", "1Q", "quest1", "q1"])
    def test_rejects_invalid_formats(self, bad):
        with pytest.raises(adquest.QuestError, match="Invalid quest ID"):
            validate_qid(bad)


# --- cmd_quest tests ---

class TestCmdQuest:
    def test_adds_quest(self, capsys):
        args = argparse.Namespace(
            desc="Test quest", xp=15, type="main",
            tag=None, priority="med"
        )
        adquest.cli.cmd_quest(args)
        state = _read_state()
        assert "Q1" in state["quests"]
        assert state["quests"]["Q1"]["desc"] == "Test quest"
        assert state["quests"]["Q1"]["xp"] == 15
        assert state["quests"]["Q1"]["type"] == "main"
        assert state["quests"]["Q1"]["status"] == "active"

    def test_default_xp_is_10(self, capsys):
        args = argparse.Namespace(
            desc="Default XP quest", xp=None, type="main",
            tag=None, priority="med"
        )
        adquest.cli.cmd_quest(args)
        state = _read_state()
        assert state["quests"]["Q1"]["xp"] == 10

    def test_rejects_empty_description(self, capsys):
        args = argparse.Namespace(
            desc="", xp=10, type="main",
            tag=None, priority="med"
        )
        with pytest.raises(adquest.QuestError, match="cannot be empty"):
            adquest.cli.cmd_quest(args)
        state = _read_state()
        assert len(state["quests"]) == 0

    def test_rejects_negative_xp(self, capsys):
        args = argparse.Namespace(
            desc="Bad XP", xp=-5, type="main",
            tag=None, priority="med"
        )
        with pytest.raises(adquest.QuestError, match="positive"):
            adquest.cli.cmd_quest(args)
        state = _read_state()
        assert len(state["quests"]) == 0

    def test_side_quest_type(self, capsys):
        args = argparse.Namespace(
            desc="Side task", xp=5, type="side",
            tag=None, priority="med"
        )
        adquest.cli.cmd_quest(args)
        state = _read_state()
        assert state["quests"]["Q1"]["type"] == "side"

    def test_tags_are_parsed(self, capsys):
        args = argparse.Namespace(
            desc="Tagged quest", xp=5, type="main",
            tag="work,urgent", priority="high"
        )
        adquest.cli.cmd_quest(args)
        state = _read_state()
        assert state["quests"]["Q1"]["tags"] == ["work", "urgent"]
        assert state["quests"]["Q1"]["priority"] == "high"


# --- cmd_done tests ---

class TestCmdDone:
    def _add_quest(self, qid="Q1", xp=10):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"][qid] = {
            "desc": "Test",
            "xp": xp,
            "status": "active",
            "type": "main",
            "focus": False,
            "tags": [],
            "priority": "med",
            "parent": None,
            "children": [],
            "chain": None,
            "created": "2026-07-01T10:00:00",
            "completed": None,
        }
        _seed_state(blob)

    def test_completes_quest_and_awards_xp(self, capsys):
        self._add_quest("Q1", xp=15)
        args = argparse.Namespace(quest_id="Q1")
        adquest.cli.cmd_done(args)
        state = _read_state()
        assert state["quests"]["Q1"]["status"] == "done"
        assert state["xp"] == 15

    def test_rejects_invalid_quest_id(self, capsys):
        args = argparse.Namespace(quest_id="ABC")
        with pytest.raises(adquest.QuestError, match="Invalid quest ID"):
            adquest.cli.cmd_done(args)

    def test_rejects_nonexistent_quest(self, capsys):
        args = argparse.Namespace(quest_id="Q99")
        with pytest.raises(adquest.QuestError, match="not found"):
            adquest.cli.cmd_done(args)

    def test_rejects_already_done(self, capsys):
        self._add_quest("Q1")
        args = argparse.Namespace(quest_id="Q1")
        adquest.cli.cmd_done(args)
        with pytest.raises(adquest.QuestError, match="already completed"):
            adquest.cli.cmd_done(args)

    def test_parent_auto_completes(self, capsys):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"]["Q1"] = {
            "desc": "Parent", "xp": 10, "status": "active",
            "type": "main", "focus": False, "tags": [], "priority": "med",
            "parent": None, "children": ["Q1.1"],
            "chain": None, "created": "2026-07-01T10:00:00", "completed": None,
        }
        blob["quests"]["Q1.1"] = {
            "desc": "Child", "xp": 5, "status": "active",
            "type": "main", "focus": False, "tags": [], "priority": "med",
            "parent": "Q1", "children": [],
            "chain": None, "created": "2026-07-01T10:00:00", "completed": None,
        }
        _seed_state(blob)
        args = argparse.Namespace(quest_id="Q1.1")
        adquest.cli.cmd_done(args)
        state = _read_state()
        assert state["quests"]["Q1"]["status"] == "done"
        assert state["xp"] == 10  # 5 (child) + 5 (bonus)

    def test_levelup_on_done(self, capsys):
        self._add_quest("Q1", xp=100)
        args = argparse.Namespace(quest_id="Q1")
        adquest.cli.cmd_done(args)
        state = _read_state()
        assert state["level"] == 2
        assert state["xp"] == 0  # 100 - 100 (threshold)

    def test_error_leaves_state_untouched(self, capsys):
        """A failing command must not persist partial mutations (commit boundary)."""
        self._add_quest("Q1", xp=15)
        args = argparse.Namespace(quest_id="Q99")  # not found → error
        with pytest.raises(adquest.QuestError):
            adquest.cli.cmd_done(args)
        state = _read_state()
        assert state["xp"] == 0
        assert state["quests"]["Q1"]["status"] == "active"


# --- cmd_log tests ---

class TestCmdLog:
    def _add_done_quest(self, qid="Q1", xp=10):
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"][qid] = {
            "desc": "Done quest", "xp": xp, "status": "done",
            "type": "main", "focus": False, "tags": [], "priority": "med",
            "parent": None, "children": [],
            "chain": None, "created": "2026-07-01T10:00:00",
            "completed": d.today().isoformat() + "T12:00:00",
        }
        _seed_state(blob)

    def test_logs_done_quests(self, capsys):
        self._add_done_quest("Q1")
        args = argparse.Namespace()
        adquest.cli.cmd_log(args)
        state = _read_state()
        # Quest moved to history
        assert "Q1" not in state["quests"]
        assert any(h["id"] == "Q1" for h in state["history"])
        # Log file created
        log_file = _test_logs_dir / f"log-{d.today().isoformat()}.md"
        assert log_file.exists()
        content = log_file.read_text()
        assert "Q1" in content
        assert "Done quest" in content

    def test_no_done_quests(self, capsys):
        args = argparse.Namespace()
        adquest.cli.cmd_log(args)
        captured = capsys.readouterr()
        assert "No completed" in captured.out

    def test_history_capped_at_50(self, capsys):
        blob = deepcopy(DEFAULT_STATE)
        # Add 55 done quests
        for i in range(1, 56):
            blob["quests"][f"Q{i}"] = {
                "desc": f"Quest {i}", "xp": 1, "status": "done",
                "type": "main", "focus": False, "tags": [], "priority": "med",
                "parent": None, "children": [],
                "chain": None, "created": "2026-07-01T10:00:00",
                "completed": d.today().isoformat() + "T12:00:00",
            }
        _seed_state(blob)
        args = argparse.Namespace()
        adquest.cli.cmd_log(args)
        state = _read_state()
        assert len(state["history"]) == 50


# --- State integrity tests ---

class TestStateIntegrity:
    def test_corrupted_state_falls_back_to_default(self, capsys):
        # Ensure no backup exists
        backup = _test_state_file.with_suffix(".json.bak")
        if backup.exists():
            backup.unlink()
        _test_state_file.write_text("not valid json {{{")
        with FileStore() as store:
            state = store.load()
        assert state == DEFAULT_STATE

    def test_corrupted_state_uses_backup(self, capsys):
        # Write a valid backup
        valid_state = deepcopy(DEFAULT_STATE)
        valid_state["xp"] = 42
        backup = _test_state_file.with_suffix(".json.bak")
        backup.write_text(json.dumps(valid_state))
        # Corrupt the main file
        _test_state_file.write_text("corrupted!")
        with FileStore() as store:
            state = store.load()
        assert state["xp"] == 42

    def test_save_creates_backup(self):
        with FileStore() as store:
            player = store.get_player()
            player["xp"] = 99
            store.update_player(player)
            store.commit()
        backup = _test_state_file.with_suffix(".json.bak")
        assert backup.exists()
        backup_data = json.loads(backup.read_text())
        # Backup should be the previous state (default with xp=0)
        assert backup_data["xp"] == 0

    def test_missing_state_file_returns_default(self):
        _test_state_file.unlink()
        with FileStore() as store:
            state = store.load()
        assert state["level"] == 1
        assert state["xp"] == 0
        assert state["quests"] == {}


# --- Input validation tests ---

class TestInputValidation:
    def test_quest_whitespace_only_rejected(self, capsys):
        args = argparse.Namespace(
            desc="   ", xp=10, type="main",
            tag=None, priority="med"
        )
        with pytest.raises(adquest.QuestError):
            adquest.cli.cmd_quest(args)
        state = _read_state()
        assert len(state["quests"]) == 0

    def test_done_bad_id_format(self, capsys):
        messages = []
        for bad_id in ["", "Q", "Q-1", "hello", "1Q", "Q1.1.1"]:
            with pytest.raises(adquest.QuestError) as excinfo:
                adquest.cli.cmd_done(argparse.Namespace(quest_id=bad_id))
            messages.append(str(excinfo.value))
        # All should have been rejected; most with the format message
        assert sum("Invalid quest ID" in m for m in messages) >= 4

    def test_sub_bad_parent_id(self, capsys):
        args = argparse.Namespace(
            parent="INVALID", desc="Sub", xp=5, tag=None
        )
        with pytest.raises(adquest.QuestError, match="Invalid quest ID"):
            adquest.cli.cmd_sub(args)

    def test_drain_negative_rejected(self, capsys):
        args = argparse.Namespace(hp=-5, mp=5, reason="test")
        with pytest.raises(adquest.QuestError, match="positive"):
            adquest.cli.cmd_drain(args)

    def test_drain_empty_reason_rejected(self, capsys):
        args = argparse.Namespace(hp=5, mp=5, reason="   ")
        with pytest.raises(adquest.QuestError, match="reason"):
            adquest.cli.cmd_drain(args)

    def test_rest_unknown_activity_rejected(self, capsys):
        args = argparse.Namespace(activity="feast")
        with pytest.raises(adquest.QuestError, match="Unknown activity"):
            adquest.cli.cmd_rest(args)

    def test_edit_no_changes_rejected(self, capsys):
        adquest.cli.cmd_quest(argparse.Namespace(
            desc="Editable quest", xp=10, type="main", tag=None, priority="med"
        ))
        args = argparse.Namespace(
            quest_id="Q1", desc=None, xp=None, type=None, tag=None, priority=None
        )
        with pytest.raises(adquest.QuestError, match="Nothing to change"):
            adquest.cli.cmd_edit(args)


# --- Idle view tests ---

class TestCmdIdle:
    def test_counts_only_top_level_quests(self, capsys):
        """Sub-quests are listed under parents; the cold-count must not
        include them (regression: count used to include hidden sub-quests)."""
        blob = deepcopy(DEFAULT_STATE)
        blob["quests"]["Q1"] = {
            "desc": "Old parent", "xp": 10, "status": "active",
            "type": "main", "focus": False, "tags": [], "priority": "med",
            "parent": None, "children": ["Q1.1"],
            "chain": None, "created": "2026-01-01T10:00:00", "completed": None,
        }
        blob["quests"]["Q1.1"] = {
            "desc": "Old sub", "xp": 5, "status": "active",
            "type": "main", "focus": False, "tags": [], "priority": "med",
            "parent": "Q1", "children": [],
            "chain": None, "created": "2026-01-01T10:00:00", "completed": None,
        }
        _seed_state(blob)
        adquest.cli.cmd_idle(argparse.Namespace(days=3))
        captured = capsys.readouterr()
        assert "1 quest(s) growing cold" in captured.out


# --- Helper function tests ---

class TestHelpers:
    def test_colored_ansi(self):
        adquest.render.FORMAT = "ansi"
        result = colored("hello", adquest.render.C_GREEN)
        assert "\033[32m" in result
        assert "hello" in result

    def test_colored_chat(self):
        adquest.render.FORMAT = "chat"
        result = colored("hello", adquest.render.C_GREEN)
        assert result == "hello"
        adquest.render.FORMAT = "ansi"  # reset

    def test_bar_full(self):
        adquest.render.FORMAT = "ansi"
        result = bar(100, 100, width=10)
        assert "█" * 10 in result

    def test_bar_empty(self):
        adquest.render.FORMAT = "ansi"
        result = bar(0, 100, width=10)
        assert "░" * 10 in result

    def test_quest_type_default(self):
        assert quest_type({}) == "main"
        assert quest_type({"type": "side"}) == "side"

    def test_quest_focus_default(self):
        assert quest_focus({}) is False
        assert quest_focus({"focus": True}) is True

    def test_quest_tags_default(self):
        assert quest_tags({}) == []
        assert quest_tags({"tags": ["a", "b"]}) == ["a", "b"]

    def test_quest_priority_default(self):
        assert quest_priority({}) == "med"
        assert quest_priority({"priority": "high"}) == "high"
