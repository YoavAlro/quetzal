"""Answerer agent clients.

The benchmark drives a real coding-agent CLI (Claude Code, Codex, Cursor) in
headless mode against the repo and records the harness's own answer and token
usage. Testing the actual harness — not a raw-API reimplementation — is the
point: the system prompt, tool loop, and context-gathering are what we measure.
"""

from quetzal.agents.base import AgentClient, build_prompt
from quetzal.agents.registry import available_agents, build_agent, list_agents

__all__ = ["AgentClient", "build_prompt", "available_agents", "build_agent", "list_agents"]
