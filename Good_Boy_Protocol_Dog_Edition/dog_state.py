"""
dog_state.py

Luna does not have an API. Luna has a nervous system and a very small
vocabulary. This file is our best attempt at giving her a schema.

State lives in a JSON file so the MCP server (a separate process) and the
Streamlit dashboard (another separate process) can both read and write it
without needing a real database, a message queue, or any other piece of
infrastructure that would be overkill for one imaginary dog.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

STATE_PATH = Path(__file__).parent / "luna_state.json"

DEFAULT_STATE: dict[str, Any] = {
    "name": "Luna",
    "energy": 90,       # 0 = comatose, 100 = feral
    "boredom": 20,      # 0 = fully entertained, 100 = plotting revenge
    "tail_wag": 60,      # 0 = still, 100 = helicopter mode
    "treats_today": 0,
    "last_meal_ts": time.time() - 60 * 60 * 2,   # pretend she ate 2h ago
    "last_walk_ts": time.time() - 60 * 60 * 5,   # pretend her last walk was 5h ago
    "last_action": "app started",
    "action_log": [],
}


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, value)))


def _load() -> dict[str, Any]:
    if not STATE_PATH.exists():
        _save(DEFAULT_STATE.copy())
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def _save(state: dict[str, Any]) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _log(state: dict[str, Any], action: str) -> None:
    state["last_action"] = action
    state["action_log"].append({"action": action, "ts": time.time()})
    state["action_log"] = state["action_log"][-20:]  # keep it short, Luna has no long-term memory either


def reset() -> dict[str, Any]:
    """Wipe Luna back to factory settings. Useful when the demo goes sideways."""
    state = DEFAULT_STATE.copy()
    state["last_meal_ts"] = time.time() - 60 * 60 * 2
    state["last_walk_ts"] = time.time() - 60 * 60 * 5
    state["action_log"] = []
    _save(state)
    return state


def get_state() -> dict[str, Any]:
    return _load()


# --- derived getters: the things a confident-but-wrong owner would guess at ---

def minutes_since_last_meal() -> float:
    state = _load()
    return round((time.time() - state["last_meal_ts"]) / 60, 1)


def minutes_since_last_walk() -> float:
    state = _load()
    return round((time.time() - state["last_walk_ts"]) / 60, 1)


def treats_today() -> int:
    return _load()["treats_today"]


def energy_level() -> int:
    return _load()["energy"]


def boredom_level() -> int:
    return _load()["boredom"]


def tail_wag_speed() -> int:
    return _load()["tail_wag"]


# --- actions: the only way to actually change how Luna feels ---

def feed(amount: int = 25) -> dict[str, Any]:
    state = _load()
    state["last_meal_ts"] = time.time()
    state["energy"] = _clamp(state["energy"] + amount * 0.2)
    state["boredom"] = _clamp(state["boredom"] + 5)  # food is not a personality
    _log(state, "fed")
    _save(state)
    return state


def give_treat() -> dict[str, Any]:
    state = _load()
    state["treats_today"] += 1
    state["tail_wag"] = _clamp(state["tail_wag"] + 15)
    state["boredom"] = _clamp(state["boredom"] - 5)
    _log(state, "gave treat")
    _save(state)
    return state


def take_for_walk() -> dict[str, Any]:
    state = _load()
    state["last_walk_ts"] = time.time()
    state["energy"] = _clamp(state["energy"] - 45)
    state["boredom"] = _clamp(state["boredom"] - 60)
    state["tail_wag"] = _clamp(state["tail_wag"] + 80)
    _log(state, "taken for walk")
    _save(state)
    return state


def play(minutes: int = 10) -> dict[str, Any]:
    state = _load()
    state["energy"] = _clamp(state["energy"] - minutes * 1.5)
    state["boredom"] = _clamp(state["boredom"] - minutes * 3)
    state["tail_wag"] = _clamp(state["tail_wag"] + minutes * 4)
    _log(state, f"played for {minutes} minutes")
    _save(state)
    return state


def ignore() -> dict[str, Any]:
    """Do nothing. Luna notices. Luna always notices."""
    state = _load()
    state["boredom"] = _clamp(state["boredom"] + 10)
    state["tail_wag"] = _clamp(state["tail_wag"] - 10)
    _log(state, "ignored")
    _save(state)
    return state


if __name__ == "__main__":
    # quick manual sanity check, not a real test suite, don't @ me
    reset()
    print("Initial:", get_state())
    print("After walk:", take_for_walk())
