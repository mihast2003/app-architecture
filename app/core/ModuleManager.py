from __future__ import annotations

import importlib.util
import tomllib

from pathlib import Path

from app.core.architecture import Component, Module

from dataclasses import dataclass, field, asdict
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from app.core.ServiceManager import ServiceManager

@dataclass
class ModuleData():
    name: str
    version: str
    id: str
    priority: int

    provides: dict[str, str]
    requires: dict[str, str]

    entry_point_filepath: Path
    entry_point_classname: str
    metadata_filepath: Path


class ModuleManager(Module):
    def __init__(self) -> None:
        self.children = [] # must have because its the root of ownership tree

        self.all_modules_data: list[ModuleData] = []

        self.active_modules: list[Module] = []

        self.on_init()

    def on_init(self):
        self.module_finder = ModuleFinder(parent=self)

    def discover_modules(self, modules_dir):
        self.all_modules_data = self.module_finder.discover_modules(modules_dir)
        # print(self.all_modules_data)

    def index_modules(self):
        self.module_indexer = ModuleIndexer(parent=self)
        self.module_indexer.index(self.all_modules_data)

    def resolve_dependencies(self):
        self.module_resolver = DependencyResolver(parent=self)
        self.providers, self.dependencies = self.module_resolver.resolve(self.module_indexer)

    def start_services(self):
        self.service_manager = ServiceManager(parent=self)

        for service_name, moduledata in self.providers.items():
            module = self.module_finder.get_module(moduledata)
            self._add_module(module, moduledata)
            self.service_manager.register(name=service_name, module=module)
            print(f"Added module '{moduledata.name}' as service '{service_name}'")

    def _add_module(self, module, moduledata):
        self.active_modules.append(module)

    # def connect_services(self, role: str, service: Module):
    #     for module in self.active_modules:
    #         required_services = self.all_modules_data[module]
    #         for service in required_services:
    #             service_module = self.service_manager.get(service)
    #             module.connect(service=service, module=service_module)

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
            id = metadata["id"]
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
        
        if not isinstance(id, str):
            raise ValueError("'id' must be a string")
        
        if not isinstance(class_name, str):
            raise ValueError("Entry point and class name must be a string")

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
            id=id,
            priority=priority,
            provides=provides,
            requires=requires,
            entry_point_filepath=entry_point_filepath,
            entry_point_classname=class_name,
            metadata_filepath=metadata_filepath,
        )
    
    def _get_module_entry_point(self, metadata_path, metadata) -> tuple[Path, Any, str]:
        """
        :return: (entry_point_filepath, spec, class_name) from metadata
        :rtype: tuple[Path, ModuleSpec, str]
        """ 
        name = metadata['name']
        entry_point = metadata.get("entry_point", "module:Module")
        module_file_name, class_name = entry_point.split(":")
        entry_point_filepath = metadata_path.parent / (module_file_name.replace(".", "/") + ".py")

        if not entry_point_filepath.is_file():
            raise FileNotFoundError(entry_point_filepath)

        spec = self._get_spec(name=name, entry_point_filepath=entry_point_filepath)

        return entry_point_filepath, spec, class_name
    

    def _get_spec(self, name, entry_point_filepath):
        spec = importlib.util.spec_from_file_location(f"app_module_{name}", entry_point_filepath)

        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module: {entry_point_filepath}")
        
        return spec


    def get_module(self, moduledata: ModuleData) -> Module:
        # entry_point_filepath, spec, class_name = self._get_module_entry_point(modu, metadata)

        spec = self._get_spec(name=moduledata.name, entry_point_filepath=moduledata.entry_point_filepath)

        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load module {moduledata.name}")
        
        imported_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported_module)

        class_name = moduledata.entry_point_classname

        module_class = getattr(imported_module, class_name)

        if not isinstance(module_class, type) or not issubclass(module_class, Module):
            raise TypeError(
                f"{class_name} must inherit from Module"
            )

        instance = module_class(parent=self.parent)
        instance.metadata = asdict(moduledata)

        return instance


class ModuleIndexer(Component):
    def on_init(self) -> None:
        self.by_provided_service: dict[str, list[ModuleData]] = {}
        self.by_name: dict[str, ModuleData] = {}
    
    def index(self, modules: list[ModuleData]):
        self.by_provided_service.clear()

        for module in modules:
            # Index by name and raise an error if name repeats
            if module.name in self.by_name:
                raise ValueError(f"Duplicate module name: '{module.name}'")
            self.by_name[module.name] = module

            # Index by provided service
            for service in module.provides:
                self.by_provided_service.setdefault(service, []).append(module)

        print("modules indexed")


class DependencyResolver(Component):
    def resolve(self, indexer: ModuleIndexer) -> tuple[dict[str, ModuleData], dict[str, list[ModuleData]]]:
        self.providers: dict[str, ModuleData] = {}
        self.dependencies: dict[str, list[ModuleData]] = {}

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