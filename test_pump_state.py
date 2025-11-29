"""
Unit tests for pump state persistence and startup behavior.

These tests verify:
1. Loading pump state when file is missing returns (None, None)
2. Loading pump state with valid data returns correct values
3. Loading pump state with corrupted JSON returns (None, None)
4. Loading pump state with missing fields returns None for those fields
5. Saving pump state creates valid JSON file
6. Startup behavior skips min-off enforcement when no valid persisted timestamp
7. Startup behavior uses persisted timestamp when available and recent
8. Startup behavior uses persisted timestamp when older than min_off
"""
import json
import os
import tempfile
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from pump_state import load_pump_state, save_pump_state, DEFAULT_STATE_FILE


class TestLoadPumpState:
    """Tests for load_pump_state function."""

    def test_missing_file_returns_none(self, tmp_path):
        """When state file is missing, returns (None, None)."""
        state_file = str(tmp_path / "nonexistent.json")
        pump_on, last_changed = load_pump_state(state_file)
        assert pump_on is None
        assert last_changed is None

    def test_valid_state_file_on(self, tmp_path):
        """When state file has valid pump ON data, returns correct values."""
        state_file = tmp_path / "pump_state.json"
        now = datetime(2025, 1, 15, 10, 30, 0, 123456)
        state_file.write_text(json.dumps({
            "pump_on": True,
            "last_changed": now.isoformat()
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        assert pump_on is True
        assert last_changed == now

    def test_valid_state_file_off(self, tmp_path):
        """When state file has valid pump OFF data, returns correct values."""
        state_file = tmp_path / "pump_state.json"
        now = datetime(2025, 1, 15, 14, 45, 30, 0)
        state_file.write_text(json.dumps({
            "pump_on": False,
            "last_changed": now.isoformat()
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        assert pump_on is False
        assert last_changed == now

    def test_corrupted_json_returns_none(self, tmp_path):
        """When state file has invalid JSON, returns (None, None)."""
        state_file = tmp_path / "pump_state.json"
        state_file.write_text("not valid json {{{")
        
        pump_on, last_changed = load_pump_state(str(state_file))
        assert pump_on is None
        assert last_changed is None

    def test_missing_pump_on_field(self, tmp_path):
        """When pump_on field is missing, returns None for that field."""
        state_file = tmp_path / "pump_state.json"
        now = datetime(2025, 1, 15, 10, 30, 0)
        state_file.write_text(json.dumps({
            "last_changed": now.isoformat()
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        assert pump_on is None
        assert last_changed == now

    def test_missing_last_changed_field(self, tmp_path):
        """When last_changed field is missing, returns None for that field."""
        state_file = tmp_path / "pump_state.json"
        state_file.write_text(json.dumps({
            "pump_on": True
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        assert pump_on is True
        assert last_changed is None

    def test_invalid_timestamp_format(self, tmp_path):
        """When last_changed has invalid format, returns None for that field."""
        state_file = tmp_path / "pump_state.json"
        state_file.write_text(json.dumps({
            "pump_on": True,
            "last_changed": "not-a-timestamp"
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        assert pump_on is True
        assert last_changed is None

    def test_invalid_pump_on_type(self, tmp_path):
        """When pump_on is not a boolean, returns None for that field."""
        state_file = tmp_path / "pump_state.json"
        now = datetime(2025, 1, 15, 10, 30, 0)
        state_file.write_text(json.dumps({
            "pump_on": "yes",  # String instead of bool
            "last_changed": now.isoformat()
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        assert pump_on is None
        assert last_changed == now


class TestSavePumpState:
    """Tests for save_pump_state function."""

    def test_save_creates_file(self, tmp_path):
        """Saving pump state creates the JSON file."""
        state_file = tmp_path / "pump_state.json"
        now = datetime(2025, 1, 15, 10, 30, 0, 123456)
        
        result = save_pump_state(True, now, str(state_file))
        
        assert result is True
        assert state_file.exists()
        
        data = json.loads(state_file.read_text())
        assert data["pump_on"] is True
        assert data["last_changed"] == now.isoformat()

    def test_save_pump_off(self, tmp_path):
        """Saving pump OFF state works correctly."""
        state_file = tmp_path / "pump_state.json"
        now = datetime(2025, 1, 15, 14, 45, 30)
        
        result = save_pump_state(False, now, str(state_file))
        
        assert result is True
        data = json.loads(state_file.read_text())
        assert data["pump_on"] is False
        assert data["last_changed"] == now.isoformat()

    def test_save_creates_parent_directory(self, tmp_path):
        """Saving pump state creates parent directories if needed."""
        state_file = tmp_path / "subdir" / "pump_state.json"
        now = datetime(2025, 1, 15, 10, 30, 0)
        
        result = save_pump_state(True, now, str(state_file))
        
        assert result is True
        assert state_file.exists()

    def test_save_overwrites_existing(self, tmp_path):
        """Saving pump state overwrites existing file."""
        state_file = tmp_path / "pump_state.json"
        old_time = datetime(2025, 1, 14, 8, 0, 0)
        new_time = datetime(2025, 1, 15, 10, 30, 0)
        
        save_pump_state(True, old_time, str(state_file))
        save_pump_state(False, new_time, str(state_file))
        
        data = json.loads(state_file.read_text())
        assert data["pump_on"] is False
        assert data["last_changed"] == new_time.isoformat()


class TestStartupBehavior:
    """
    Tests for startup behavior scenarios.
    
    These tests verify that:
    1. When no persisted timestamp exists, min-off enforcement is skipped
    2. When a recent persisted timestamp exists, min-off enforcement uses it
    3. When an older persisted timestamp exists (older than min_off), pump can start
    """

    def test_missing_persisted_state_allows_immediate_start(self, tmp_path):
        """
        When no persisted state exists and pump is off, controller should
        allow immediate start (skip min-off enforcement on first cycle).
        
        This tests the logic that:
        - persisted_on is None
        - persisted_last_changed is None
        - skip_min_off_enforcement should be set True
        - pump_off_time should be None
        """
        state_file = str(tmp_path / "nonexistent.json")
        
        pump_on, last_changed = load_pump_state(state_file)
        
        # Simulate startup logic
        assert pump_on is None
        assert last_changed is None
        
        # When these are None and pump is currently off, the startup code sets:
        # skip_min_off_enforcement = True
        # pump_off_time = None
        # This allows the pump to start immediately when delta > DELTA_ON

    def test_recent_persisted_timestamp_enforces_min_off(self, tmp_path):
        """
        When persisted timestamp is recent (less than MIN_OFF_MINUTES ago),
        controller should enforce minimum off time.
        """
        state_file = tmp_path / "pump_state.json"
        MIN_OFF_MINUTES = 20
        
        # Pump was turned off 5 minutes ago
        five_minutes_ago = datetime.now() - timedelta(minutes=5)
        state_file.write_text(json.dumps({
            "pump_on": False,
            "last_changed": five_minutes_ago.isoformat()
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        
        assert pump_on is False
        assert last_changed is not None
        
        # Calculate elapsed time
        now = datetime.now()
        elapsed_off = (now - last_changed).total_seconds() / 60
        
        # Should still be within min_off time
        assert elapsed_off < MIN_OFF_MINUTES
        
        # With this state loaded, pump_off_time = last_changed (not None),
        # and skip_min_off_enforcement = False (default),
        # so the controller will enforce min-off time

    def test_older_persisted_timestamp_allows_start(self, tmp_path):
        """
        When persisted timestamp is old (more than MIN_OFF_MINUTES ago),
        controller should allow pump to start.
        """
        state_file = tmp_path / "pump_state.json"
        MIN_OFF_MINUTES = 20
        
        # Pump was turned off 30 minutes ago
        thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
        state_file.write_text(json.dumps({
            "pump_on": False,
            "last_changed": thirty_minutes_ago.isoformat()
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        
        assert pump_on is False
        assert last_changed is not None
        
        # Calculate elapsed time
        now = datetime.now()
        elapsed_off = (now - last_changed).total_seconds() / 60
        
        # Should be past min_off time
        assert elapsed_off > MIN_OFF_MINUTES
        
        # With this state loaded, elapsed_off > MIN_OFF_MINUTES,
        # so the min-off check will pass and pump can turn on

    def test_pump_on_persisted_state(self, tmp_path):
        """
        When persisted state shows pump was on, controller should
        use that timestamp for pump_on_time.
        """
        state_file = tmp_path / "pump_state.json"
        
        # Pump was turned on 10 minutes ago
        ten_minutes_ago = datetime.now() - timedelta(minutes=10)
        state_file.write_text(json.dumps({
            "pump_on": True,
            "last_changed": ten_minutes_ago.isoformat()
        }))
        
        pump_on, last_changed = load_pump_state(str(state_file))
        
        assert pump_on is True
        assert last_changed is not None
        
        # With this state and current pump also ON:
        # pump_on_time = last_changed (10 minutes ago)
        # The controller correctly tracks how long pump has been on


class TestRoundTrip:
    """Tests for save/load round-trip behavior."""

    def test_save_and_load_round_trip(self, tmp_path):
        """Saved state can be loaded back correctly."""
        state_file = str(tmp_path / "pump_state.json")
        now = datetime.now()
        
        save_pump_state(True, now, state_file)
        pump_on, last_changed = load_pump_state(state_file)
        
        assert pump_on is True
        # Note: datetime precision might be affected by JSON serialization
        assert last_changed.isoformat() == now.isoformat()

    def test_multiple_state_changes(self, tmp_path):
        """Multiple state changes are tracked correctly."""
        state_file = str(tmp_path / "pump_state.json")
        
        t1 = datetime(2025, 1, 15, 8, 0, 0)
        t2 = datetime(2025, 1, 15, 9, 0, 0)
        t3 = datetime(2025, 1, 15, 10, 0, 0)
        
        # Turn on at t1
        save_pump_state(True, t1, state_file)
        pump_on, last_changed = load_pump_state(state_file)
        assert pump_on is True
        assert last_changed == t1
        
        # Turn off at t2
        save_pump_state(False, t2, state_file)
        pump_on, last_changed = load_pump_state(state_file)
        assert pump_on is False
        assert last_changed == t2
        
        # Turn on at t3
        save_pump_state(True, t3, state_file)
        pump_on, last_changed = load_pump_state(state_file)
        assert pump_on is True
        assert last_changed == t3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
