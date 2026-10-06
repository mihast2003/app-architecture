from __future__ import annotations

import importlib.util
import tomllib

from pathlib import Path

from app.core.architecture import Component, Module

from dataclasses import dataclass, field, asdict
from typing import Any

from packaging.specifiers import SpecifierSet, InvalidSpecifier
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

        self.active_modules_by_id: dict[str, Module] = {}

        self.on_init()

    def on_init(self):
        self.module_finder = ModuleFinder(parent=self)

    def discover_modules(self, modules_dir):
        self.all_modules_data = self.module_finder.discover_modules(modules_dir)
        # print(self.all_modules_data)

    def index_modules(self):
        self.moduledata_by_id = {module.id: module for module in self.all_modules_data}

    def resolve_dependencies(self):
        self.module_resolver = DependencyResolver(parent=self)
        self.resolved_services = self.module_resolver.resolve(self.all_modules_data)

    def connect_services(self):
        self.service_manager = ServiceManager(parent=self)

        self.index_modules()

        self._add_all_modules()

        for service_name, provider_data in self.resolved_services.items():
            provider_instance = self.active_modules_by_id[provider_data.id]
            self.service_manager.register_service(service_name, provider_instance)
            print(f"Added module '{provider_data.id}' as service '{service_name}'")

        for module_id in self.active_modules_by_id:
            instance = self.active_modules_by_id[module_id]
            module_data = self.moduledata_by_id[module_id]

            for service_name in module_data.requires:
                instance.connect(service_name, self.service_manager.get_service(service_name))


    def _add_all_modules(self):
        for _, moduledata in self.moduledata_by_id.items():
            self._add_module(moduledata)

    def _add_module(self, moduledata: ModuleData):
        module = self._instantiate_module(moduledata)
        self.active_modules_by_id[moduledata.id] = module


    def _instantiate_module(self, moduledata: ModuleData) -> Module:
        spec = self.module_finder.get_spec(name=moduledata.name, entry_point_filepath=moduledata.entry_point_filepath)

        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load module {moduledata.name}")
        
        imported_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported_module)

        class_name = moduledata.entry_point_classname

        module_class = getattr(imported_module, class_name)

        if not isinstance(module_class, type) or not issubclass(module_class, Module):
            raise TypeError(f"{class_name} must inherit from Module")

        instance = module_class(parent=self)
        instance.metadata = asdict(moduledata)

        return instance


# region all_helpers
    def start_all(self):
        for module in self.active_modules_by_id.values():
            module._init()

    def load_all(self):
        for module in self.active_modules_by_id.values():
            module._load()

    def unload_all(self):
        for module in reversed(self.active_modules_by_id.values()):
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

        spec = self.get_spec(name=name, entry_point_filepath=entry_point_filepath)

        return entry_point_filepath, spec, class_name
    

    def get_spec(self, name, entry_point_filepath):
        spec = importlib.util.spec_from_file_location(f"app_module_{name}", entry_point_filepath)

        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module: {entry_point_filepath}")
        
        return spec



class DependencyResolver(Component):
    def resolve(self, modules: list[ModuleData]) -> dict[str, ModuleData]:
        # service -> providers
        providers: dict[str, list[ModuleData]] = {}

        # service -> modules requiring it
        requirements: dict[str, list[ModuleData]] = {}

        for module in modules:
            for service, version in module.provides.items():
                providers.setdefault(service, []).append(module)

            for service, requirement in module.requires.items():
                requirements.setdefault(service, []).append(module)

        # service -> selected provider
        resolved_services: dict[str, ModuleData] = {}

        for service, modules_requiring in requirements.items():
            candidates = providers.get(service, [])

            if not candidates:
                raise RuntimeError(f"No provider found for required service '{service}'")

            valid_candidates = []

            for provider in candidates:
                provider_version = Version(provider.provides[service])

                for module in modules_requiring:
                    try:
                        if provider_version in SpecifierSet(module.requires[service]):
                            valid_candidates.append(provider)
                    except InvalidSpecifier as e:
                        raise RuntimeError(f"Check requirements config for module {module.id}: {e}") from e
            
            
            if not valid_candidates:
                raise RuntimeError(f"No compatible provider found for service '{service}'")

            # Highest priority first, then highest version.
            provider = max(
                valid_candidates,
                key=lambda module: (module.priority, Version(module.provides[service]),),
            )

            resolved_services[service] = provider

        return resolved_services