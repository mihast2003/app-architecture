from __future__ import annotations

import importlib.util
import tomllib

from pathlib import Path

from app.core.architecture import Component, Module

from dataclasses import dataclass, field
from typing import Any

@dataclass
class ModuleData():
    name: str
    metadata: dict
    path: Path


class ModuleManager():
    def __init__(self) -> None:
        self.children = [] # must have because its the root of ownership tree

        self.all_metadata: list[ModuleData] = []

        self.modules: list[Module] = []

        self.on_init()

    def on_init(self):
        self.module_finder = ModuleFinder(parent=self)

    def load_core_modules(self, modules_dir):
        modules = self.module_finder.load_core_modules(modules_dir)
        self.modules = modules

    def discover_modules(self, modules_dir):
        self.all_metadata = self.module_finder.discover_modules(modules_dir)
        print(self.all_metadata)


# region all_helpers
    def start_all(self):
        for module in self.modules:
            module._init()

    def load_all(self):
        for module in self.modules:
            module._load()

    def unload_all(self):
        for module in reversed(self.modules):
            module._unload()
#endregion


class ModuleFinder(Component):
    def discover_modules(self, dir) -> list[ModuleData]:
        modules_metadata: list[ModuleData] = []

        for metadata_path in dir.rglob("metadata.toml"):
            try:
                with metadata_path.open("rb") as file:
                    metadata = tomllib.load(file)
                
                new_data = ModuleData(name=metadata["name"], metadata=metadata, path=metadata_path)
                modules_metadata.append(new_data)

                print(f"Discovered module: {metadata['name']}")

            except Exception as error:
                print(
                    f"Failed to discover module at "
                    f"{metadata_path.parent}: {error}"
                )

        return modules_metadata


    def load_core_modules(self, dir) -> list:
        instances = []

        for metadata_path in dir.rglob("metadata.toml"):
            try:
                with metadata_path.open("rb") as file:
                    metadata = tomllib.load(file)

                if metadata.get("role") != "core-module":
                    continue
                
                module = self._get_module(metadata_path=metadata_path, metadata=metadata)
                instances.append(module)

                print(f"Discovered core module: {metadata['name']}")

            except Exception as error:
                print(
                    f"Failed to discover core module at "
                    f"{metadata_path.parent}: {error}"
                )

        return instances

    def _get_module(self, metadata_path, metadata) -> Module:
        entry_point = metadata.get("entry_point", "module:Module")

        module_file_name, class_name = entry_point.split(":")

        module_file = metadata_path.parent / (module_file_name.replace(".", "/") + ".py")

        if not module_file.is_file():
            raise FileNotFoundError(module_file)

        spec = importlib.util.spec_from_file_location(
            f"app_module_{metadata['name']}",
            module_file,
        )

        if spec is None or spec.loader is None:
            raise ImportError(
                f"Cannot load module: {module_file}"
            )

        imported_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported_module)

        module_class = getattr(imported_module, class_name)

        if not isinstance(module_class, type) or not issubclass(
            module_class, Module
        ):
            raise TypeError(
                f"{class_name} must inherit from Module"
            )

        instance = module_class(parent=self.parent)
        instance.metadata = metadata

        return instance
