from __future__ import annotations

from dataclasses import dataclass

from api.plugin_boundary.contracts import PluginBoundaryContractError, PluginHealthStatus


NON_EXECUTABLE_PLUGIN_STATUSES = {"FAILED", "RATE_LIMITED", "TIMEOUT", "DISABLED"}


@dataclass(frozen=True)
class PluginRegistration:
    plugin_id: str
    provider: str
    dataset_types: tuple[str, ...]
    priority: int = 100
    health: PluginHealthStatus | None = None

    def __post_init__(self) -> None:
        if not self.plugin_id.strip():
            raise PluginBoundaryContractError("plugin_id must be non-empty")
        if not self.provider.strip():
            raise PluginBoundaryContractError("provider must be non-empty")
        if not self.dataset_types:
            raise PluginBoundaryContractError("dataset_types must be non-empty")
        if self.priority < 0:
            raise PluginBoundaryContractError("priority must be non-negative")

    @property
    def executable(self) -> bool:
        return self.health is None or self.health.status not in NON_EXECUTABLE_PLUGIN_STATUSES


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PluginRegistration] = {}

    def register(self, plugin: PluginRegistration) -> None:
        self._plugins[plugin.plugin_id] = plugin

    def get(self, plugin_id: str) -> PluginRegistration | None:
        return self._plugins.get(plugin_id)

    def candidates_for_dataset_type(self, dataset_type: str) -> list[PluginRegistration]:
        return sorted(
            [
                plugin
                for plugin in self._plugins.values()
                if dataset_type in plugin.dataset_types and plugin.executable
            ],
            key=lambda plugin: (plugin.priority, plugin.plugin_id),
        )
