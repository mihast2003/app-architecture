from __future__ import annotations

from architecture import Component, Module, ModuleMetadata

from dataclasses import dataclass, field
from typing import Any


class ModuleManager(Module):
    metadata = ModuleMetadata(
        name="pet",
        version="1.0.0",
        role="core",
        requires=["app_provider"],
    )
    def __init__(self):
        self.modules: list[Module] = []

        # role -> module providing that role
        self.providers: dict[str, Module] = {}

    def register(self, module: Module):
        if not isinstance(module, Module):
            raise TypeError("Only Module instances can be registered")

        self.modules.append(module)

        # Register everything this module provides
        for role in module.metadata.provides:
            if role in self.providers:
                raise RuntimeError(
                    f"Multiple modules provide role '{role}'"
                )

            self.providers[role] = module

    def resolve_dependencies(self, module: Module):
        for role in module.metadata.requires:
            provider = self.providers.get(role)

            if provider is None:
                raise RuntimeError(
                    f"Module '{module.metadata.name}' "
                    f"requires '{role}', but no provider exists"
                )

            module.connect(role, provider)

    def load_all(self):
        # First resolve dependencies
        for module in self.modules:
            self.resolve_dependencies(module)

        # Then load modules
        for module in self.modules:
            module.load()

    def unload_all(self):
        # Reverse order is generally safer
        for module in reversed(self.modules):
            module.unload()