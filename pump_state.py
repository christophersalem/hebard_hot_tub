"""
Pump state persistence module.

This module provides functions to save and load pump state to/from a JSON file.
The state file stores:
- pump_on: bool - whether the pump is currently on
- last_changed: str (ISO 8601) - timestamp of the last state change

Persistence format (JSON):
{
    "pump_on": true|false,
    "last_changed": "2025-01-15T10:30:00.123456"
}

On load, if the file is missing or corrupted:
- Returns None for missing/invalid values
- Allows the controller to make safe startup decisions (e.g., allow immediate start)
"""
import json
import os
import logging
from datetime import datetime
from typing import Optional, Tuple

# Default state file path (in the data directory)
DEFAULT_STATE_FILE = os.path.join("data", "pump_state.json")

logger = logging.getLogger(__name__)


def load_pump_state(state_file: str = DEFAULT_STATE_FILE) -> Tuple[Optional[bool], Optional[datetime]]:
    """
    Load persisted pump state from the state file.

    Returns:
        Tuple of (pump_on, last_changed):
        - pump_on: True if pump was on, False if off, None if unknown/missing
        - last_changed: datetime of last state change, None if unknown/missing

    If the file is missing or corrupted, returns (None, None).
    """
    if not os.path.exists(state_file):
        logger.debug("State file not found: %s", state_file)
        return None, None

    try:
        with open(state_file, "r") as f:
            data = json.load(f)

        pump_on = data.get("pump_on")
        if pump_on is not None and not isinstance(pump_on, bool):
            logger.warning("Invalid pump_on value in state file: %s", pump_on)
            pump_on = None

        last_changed_str = data.get("last_changed")
        last_changed = None
        if last_changed_str:
            try:
                last_changed = datetime.fromisoformat(last_changed_str)
            except (ValueError, TypeError) as e:
                logger.warning("Invalid last_changed timestamp in state file: %s (%s)", last_changed_str, e)
                last_changed = None

        logger.debug("Loaded pump state: pump_on=%s, last_changed=%s", pump_on, last_changed)
        return pump_on, last_changed

    except json.JSONDecodeError as e:
        logger.warning("Corrupted state file (invalid JSON): %s", e)
        return None, None
    except Exception as e:
        logger.warning("Failed to load state file: %s", e)
        return None, None


def save_pump_state(pump_on: bool, last_changed: datetime, state_file: str = DEFAULT_STATE_FILE) -> bool:
    """
    Save pump state to the state file.

    Args:
        pump_on: True if pump is on, False if off
        last_changed: datetime of the state change

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Ensure the directory exists
        state_dir = os.path.dirname(state_file)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)

        data = {
            "pump_on": pump_on,
            "last_changed": last_changed.isoformat()
        }

        with open(state_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug("Saved pump state: pump_on=%s, last_changed=%s", pump_on, last_changed)
        return True

    except Exception as e:
        logger.warning("Failed to save state file: %s", e)
        return False
