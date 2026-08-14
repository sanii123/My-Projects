"""
mcp_server.py

This is the part that makes the project legitimate rather than "an LLM
guessing based on vibes." Every tool below is a genuine MCP tool, callable
by any MCP-compatible client (Claude Desktop, Claude Code, or the Gemini
adapter we wrote ourselves because Gemini doesn't speak MCP natively).

Run standalone for testing:
    python mcp_server.py

Run as a server other clients connect to over stdio:
    it's launched as a subprocess by gemini_client.py, you don't run it by hand
"""

from mcp.server.mcpserver import MCPServer

import dog_state

mcp = MCPServer("good-boy-protocol")


@mcp.tool()
def get_full_state() -> dict:
    """Return Luna's complete current state: energy, boredom, tail wag speed,
    treats today, and how long ago she was last fed and walked."""
    return dog_state.get_state()


@mcp.tool()
def get_minutes_since_last_meal() -> float:
    """Minutes elapsed since Luna's last meal."""
    return dog_state.minutes_since_last_meal()


@mcp.tool()
def get_minutes_since_last_walk() -> float:
    """Minutes elapsed since Luna's last walk."""
    return dog_state.minutes_since_last_walk()


@mcp.tool()
def get_treats_today() -> int:
    """Number of treats Luna has received today. Relevant when deciding
    whether 'give another treat' is a solution or a habit."""
    return dog_state.treats_today()


@mcp.tool()
def get_energy_level() -> int:
    """Luna's current energy, 0 (asleep) to 100 (feral)."""
    return dog_state.energy_level()


@mcp.tool()
def get_boredom_level() -> int:
    """Luna's current boredom, 0 (entertained) to 100 (plotting something)."""
    return dog_state.boredom_level()


@mcp.tool()
def get_tail_wag_speed() -> int:
    """Luna's tail wag speed, 0 (still) to 100 (helicopter)."""
    return dog_state.tail_wag_speed()


@mcp.tool()
def take_luna_for_walk() -> dict:
    """Take Luna for a walk. Drains energy and boredom significantly,
    raises tail wag speed. Use this when the evidence points to
    under-stimulation rather than hunger."""
    return dog_state.take_for_walk()


@mcp.tool()
def feed_luna() -> dict:
    """Feed Luna a meal. Resets time-since-last-meal, restores some energy.
    Use this when the evidence actually points to hunger, not boredom."""
    return dog_state.feed()


@mcp.tool()
def give_luna_treat() -> dict:
    """Give Luna a treat. Small boredom relief, raises tail wag, increments
    the daily treat counter. Cheap, but not a substitute for a walk."""
    return dog_state.give_treat()


@mcp.tool()
def play_with_luna(minutes: int = 10) -> dict:
    """Play with Luna for a given number of minutes. Drains some energy,
    reduces boredom, raises tail wag. A lighter-weight alternative to a
    full walk."""
    return dog_state.play(minutes)


@mcp.tool()
def ignore_luna() -> dict:
    """Do nothing. Luna's boredom rises and her tail wag drops. Included
    so the agent has a real 'do not intervene' option instead of always
    picking an action just because tools exist."""
    return dog_state.ignore()


if __name__ == "__main__":
    mcp.run()
