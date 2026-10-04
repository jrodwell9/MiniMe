from pathlib import Path
from typing import Any, ClassVar

from .base import AgentLogAdapter


class AgentLogAdapterFactory:
    """Factory for discovering, registering, and instantiating AgentLogAdapters."""

    _registry: ClassVar[dict[str, type[AgentLogAdapter]]] = {}

    @classmethod
    def register(cls, name: str, adapter_cls: type[AgentLogAdapter]) -> None:
        """Register an adapter class by agent name slug."""
        cls._registry[name.lower()] = adapter_cls

    @classmethod
    def list_registered(cls) -> list[str]:
        """List all registered agent adapter names."""
        return list(cls._registry.keys())

    @classmethod
    def get_adapter(cls, name: str, **kwargs: Any) -> AgentLogAdapter:
        """Instantiate a specific registered adapter by name."""
        name_clean = name.lower()
        if name_clean not in cls._registry:
            raise ValueError(
                f"Unknown agent adapter '{name}'. Registered adapters: {list(cls._registry.keys())}"
            )
        return cls._registry[name_clean](**kwargs)

    @classmethod
    def detect_available_adapters(cls, **kwargs: Any) -> list[AgentLogAdapter]:
        """
        Detect and instantiate all registered adapters whose workspace/storage
        environments exist locally on this machine.
        """
        available: list[AgentLogAdapter] = []
        for name in cls._registry:
            try:
                inst = cls._registry[name](**kwargs)
                if inst.is_available():
                    available.append(inst)
            except (OSError, TypeError, ValueError):
                continue
        return available

    @classmethod
    def get_primary_adapter(
        cls,
        agent_name: str | None = None,
        project_path: str | Path | None = None,
        mode: str = "auto",
        **kwargs: Any,
    ) -> AgentLogAdapter:
        """
        Get the preferred adapter:
        1. If agent_name is explicitly requested, return that adapter.
        2. Otherwise, return the first detected available adapter.
        3. If no adapter environment is detected, fallback to 'claude' adapter.
        """
        if agent_name and agent_name.lower() in cls._registry:
            return cls.get_adapter(
                agent_name.lower(),
                project_path=project_path,
                mode=mode,
                **kwargs,
            )

        detected = cls.detect_available_adapters(
            project_path=project_path, mode=mode, **kwargs
        )
        if detected:
            return detected[0]

        # Fallback to claude adapter
        if "claude" in cls._registry:
            return cls._registry["claude"](
                project_path=project_path, mode=mode, **kwargs
            )

        raise RuntimeError("No AgentLogAdapter registered in factory.")
