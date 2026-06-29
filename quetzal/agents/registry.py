"""Agent-client registry.

Maps an --agent name to its adapter, importing each adapter lazily so selecting
one client never requires another's dependencies (e.g. choosing claude-code does
not import another's).
"""

from __future__ import annotations

import importlib

from quetzal.agents.base import AgentClient

# name -> "module:ClassName"
_REGISTRY: dict[str, str] = {
    "claude-code": "quetzal.agents.claude_code:ClaudeCodeAgent",
    "codex": "quetzal.agents.codex:CodexAgent",
    "cursor": "quetzal.agents.cursor:CursorAgent",
    "opencode": "quetzal.agents.opencode:OpenCodeAgent",
}


def list_agents() -> list[str]:
    return list(_REGISTRY)


def _load(name: str) -> type[AgentClient]:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown agent '{name}'. Options: {', '.join(_REGISTRY)}")
    module_path, class_name = _REGISTRY[name].split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def build_agent(name: str, model: str | None = None) -> AgentClient:
    """Instantiate an agent client, erroring clearly if it is not available."""
    agent_cls = _load(name)
    if not agent_cls.is_available():
        raise RuntimeError(f"Agent '{name}' is not available. {agent_cls.install_hint}")
    return agent_cls(model=model)


def available_agents() -> dict[str, bool]:
    """Map each agent name to whether it can run here (best-effort, no import errors)."""
    status: dict[str, bool] = {}
    for name in _REGISTRY:
        try:
            status[name] = _load(name).is_available()
        except Exception:
            status[name] = False
    return status
