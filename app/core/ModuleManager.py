from __future__ import annotations

import importlib.util
import tomllib

from pathlib import Path

from app.core.architecture import Component, Module

from dataclasses import dataclass, field
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.version import Version

@dataclass
class ModuleData():
    name: str
    version: str
    role: str
    priority: int

    provides: dict[str, str]
    requires: dict[str, str]

    entry_point_filepath: Path
    metadata_filepath: Path


class ModuleManager(Module):
    def __init__(self) -> None:
        self.children = [] # must have because its the root of ownership tree

        self.all_modules_data: list[ModuleData] = []

        self.active_modules: list[Module] = []

        self.on_init()

    def on_init(self):
        self.module_finder = ModuleFinder(parent=self)

    # def load_core_modules(self, modules_dir):
    #     modules = self.module_finder.load_core_modules(modules_dir)
    #     self.modules = modules

    def discover_modules(self, modules_dir):
        self.all_modules_data = self.module_finder.discover_modules(modules_dir)
        # print(self.all_modules_data)

    def index_modules(self):
        self.module_indexer = ModuleIndexer(parent=self)
        self.module_indexer.index(self.all_modules_data)

    def reolve_dependencies(self):
        self.module_resolver = DependencyResolver(parent=self)
        self.module_resolver.resolve(self.module_indexer)


# region all_helpers
    def start_all(self):
        for module in self.active_modules:
            module._init()

    def load_all(self):
        for module in self.active_modules:
            module._load()

    def unload_all(self):
        for module in reversed(self.active_modules):
            module._unload()
#endregion


class ModuleFinder(Component):
    def discover_modules(self, dir) -> list[ModuleData]:
        modules_metadata: list[ModuleData] = []

        for metadata_filepath in dir.rglob("metadata.toml"):
            try:
                with metadata_filepath.open("rb") as file:
                    metadata = tomllib.load(file)
                
                new_module_data = self._load_module_data(metadata_filepath)
                modules_metadata.append(new_module_data)

                # print(f"Discovered module: {metadata['name']}\n", new_module_data)

            except Exception as error:
                print(
                    f"Failed to discover module at "
                    f"{metadata_filepath.parent}: {error}"
                )

        return modules_metadata


    # def load_core_modules(self, dir) -> list:
    #     instances = []

    #     for metadata_path in dir.rglob("metadata.toml"):
    #         try:
    #             with metadata_path.open("rb") as file:
    #                 metadata = tomllib.load(file)

    #             if metadata.get("role") != "core-module":
    #                 continue
                
    #             module = self._get_module(metadata_path=metadata_path, metadata=metadata)
    #             instances.append(module)

    #             print(f"Discovered core module: {metadata['name']}")

    #         except Exception as error:
    #             print(
    #                 f"Failed to discover core module at "
    #                 f"{metadata_path.parent}: {error}"
    #             )

    #     return instances

    def _load_module_data(self, metadata_filepath: Path) -> ModuleData:
        try:
            with metadata_filepath.open("rb") as file:
                metadata = tomllib.load(file)
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise ValueError(
                f"Could not read metadata file '{metadata_filepath}': {e}"
            ) from e

        try:
            name = metadata["name"]
            version = metadata["version"]
            role = metadata["role"]
            priority = metadata["priority"]
            provides = metadata["provides"]
            requires = metadata["requires"]

            entry_point_filepath, spec, class_name = self._get_module_entry_point(metadata_filepath, metadata)

        except KeyError as e:
            raise ValueError(
                f"Missing required metadata field: '{e.args[0]}'"
            ) from e

        if not isinstance(name, str):
            raise ValueError("'name' must be a string")

        if not isinstance(version, str):
            raise ValueError("'version' must be a string")

        if not isinstance(role, str):
            raise ValueError("'role' must be a string")

        if not isinstance(priority, int):
            raise ValueError("'priority' must be an integer")

        if not isinstance(provides, dict):
            raise ValueError("'provides' must be a table")

        if not isinstance(requires, dict):
            raise ValueError("'requires' must be a table")

        if not all(isinstance(k, str) and isinstance(v, str)
                for k, v in provides.items()):
            raise ValueError("'provides' must contain string keys and values")

        if not all(isinstance(k, str) and isinstance(v, str)
                for k, v in requires.items()):
            raise ValueError("'requires' must contain string keys and values")

        return ModuleData(
            name=name,
            version=version,
            role=role,
            priority=priority,
            provides=provides,
            requires=requires,
            entry_point_filepath=entry_point_filepath,
            metadata_filepath=metadata_filepath,
        )
    
    def _get_module_entry_point(self, metadata_path, metadata) -> tuple[Path, Any, str]:
        """
        :return: (entry_point_filepath, spec, class_name) from metadata
        :rtype: tuple[Path, ModuleSpec, str]
        """ 
        entry_point = metadata.get("entry_point", "module:Module")
        module_file_name, class_name = entry_point.split(":")
        entry_point_filepath = metadata_path.parent / (module_file_name.replace(".", "/") + ".py")

        if not entry_point_filepath.is_file():
            raise FileNotFoundError(entry_point_filepath)

        spec = importlib.util.spec_from_file_location(
            f"app_module_{metadata['name']}",
            entry_point_filepath,
        )

        if spec is None or spec.loader is None:
            raise ImportError(
                f"Cannot load module: {entry_point_filepath}"
            )

        return entry_point_filepath, spec, class_name


    def _get_module(self, metadata_path, metadata) -> Module:
        entry_point_filepath, spec, class_name = self._get_module_entry_point(metadata_path, metadata)

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


class ModuleIndexer(Component):
    def on_init(self) -> None:
        self.by_role: dict[str, list[ModuleData]] = {}
        self.by_provided_service: dict[str, list[ModuleData]] = {}
        self.by_name: dict[str, ModuleData] = {}
    
    def index(self, modules: list[ModuleData]):
        self.by_role.clear()
        self.by_provided_service.clear()

        for module in modules:
            # Index by name and raise an error if name repeats
            if module.name in self.by_name:
                raise ValueError(f"Duplicate module name: '{module.name}'")
            self.by_name[module.name] = module

            # Index by role
            self.by_role.setdefault(module.role, []).append(module)

            # Index by provided service
            for service in module.provides:
                self.by_provided_service.setdefault(service, []).append(module)

        print("modules indexed")



class DependencyResolver(Component):
    
    def resolve(self, indexer: ModuleIndexer) -> tuple[dict[str, ModuleData], dict[str, list[ModuleData]]]:
        self.providers: dict[str, ModuleData] = {}
        self.dependencies: dict[str, list[ModuleData]] = {}

        # Check required roles
        # required_roles = {"core-module"} # lets not do that for now
        required_roles = {}
        for role in required_roles:
            if not indexer.by_role.get(role):
                raise RuntimeError(f"No module found for required role '{role}'")


        for module_data in indexer.by_name.values():
            self.dependencies[module_data.name] = []

            for service, requirement in module_data.requires.items():

                candidates = indexer.by_provided_service.get(service, [])

                if not candidates:
                    raise RuntimeError(f"Module '{module_data.name}' requires {service} {requirement}', but no provider was found")

                compatible = [
                    candidate
                    for candidate in candidates
                    if Version(candidate.provides[service])
                    in SpecifierSet(requirement)
                ]

                if not compatible:
                    raise RuntimeError(f"Module '{module_data.name}' requires {service} {requirement}', but no compatible provider was found")

                # Prefer the highest compatible service version
                provider = max(compatible, key=lambda candidate: Version(candidate.provides[service]))

                self.providers[service] = provider
                self.dependencies[module_data.name].append(provider)

        print(self.providers)
        print(self.dependencies)
        return self.providers, self.dependencies