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

from collections import defaultdict, deque
from packaging.specifiers import SpecifierSet
from packaging.version import Version

@dataclass
class ModuleData():
    name: str
    version: str
    id: str
    priority: int
    core_module: bool

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
        pass

    def discover_modules(self, modules_dir):
        module_finder = ModuleFinder(parent=self)
        all_modules_data = module_finder.discover_modules(modules_dir)
        # print(self.all_modules_data)
        self.index_modules(all_modules_data)

    def index_modules(self, all_modules_data: list[ModuleData]):
        """Constucts different indexes of all found module data"""
        self.all_modules_data = all_modules_data
        self.moduledata_by_id = {module.id: module for module in all_modules_data}

    def resolve_dependencies(self):
        dependency_resolver = DependencyResolver(parent=self)
        self.resolved_services = dependency_resolver.resolve(self.all_modules_data)

    def resolve_load_order(self):
        load_order_resolver = LoadOrderResolver(parent=self)
        self.load_order = load_order_resolver.resolve(self.moduledata_by_id)

        print(self.load_order)

    def load_modules(self):
        for moduledata in self.load_order:
            self._add_module(moduledata)

    def _add_module(self, moduledata: ModuleData):
        module = self._instantiate_module(moduledata)
        self.active_modules_by_id[moduledata.id] = module
        print(f"instantiated module {moduledata.id}")

    def _instantiate_module(self, moduledata: ModuleData) -> Module:
        spec = self._get_spec(name=moduledata.name, entry_point_filepath=moduledata.entry_point_filepath)

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

    def _get_spec(self, name, entry_point_filepath):
        spec = importlib.util.spec_from_file_location(f"app_module_{name}", entry_point_filepath)

        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module: {entry_point_filepath}")
        
        return spec
    

    def connect_services(self):
        service_manager = ServiceManager(parent=self)

        for service_name, provider_data in self.resolved_services.items():
            provider_instance = self.active_modules_by_id[provider_data.id]
            service_manager.register_service(service_name, provider_instance)
            print(f"Added module '{provider_data.id}' as service '{service_name}'")

        for module_id in self.active_modules_by_id:
            instance = self.active_modules_by_id[module_id]
            module_data = self.moduledata_by_id[module_id]

            for service_name in module_data.requires:
                instance.connect(service_name, service_manager.get_service(service_name))


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
            raise ValueError(f"Could not read metadata file '{metadata_filepath}': {e}") from e

        try:
            name = metadata["name"]
            version = metadata["version"]
            id = metadata["id"]
            priority = metadata["priority"]
            core_module = metadata.get("core_module", False)
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
        
        if not isinstance(core_module, bool):
            raise ValueError("'core_module' must be a bool")

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

        print(f"Discovered module {name}({id})")
        return ModuleData(
            name=name,
            version=version,
            id=id,
            priority=priority,
            core_module=core_module,
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


class DependencyResolver(Component):
    def resolve(self, modules: list[ModuleData]) -> dict[str, ModuleData]:

        # service[providers]
        providers: dict[str, list[ModuleData]] = {}

        # service[modules requiring it]
        requirements: dict[str, list[ModuleData]] = {}

        for module in modules:
            for service, version in module.provides.items():
                providers.setdefault(service, []).append(module)

            for service, requirement in module.requires.items():
                requirements.setdefault(service, []).append(module)

        # service[selected provider]
        resolved_services: dict[str, ModuleData] = {}

        for service, modules_requiring in requirements.items():
            candidates = providers.get(service, [])
            print("canditaes", candidates)

            if not candidates:
                raise RuntimeError(f"No provider found for required service '{service}', which is required by {modules_requiring}")

            valid_candidates = []

            for provider in candidates:
                provider_version = Version(provider.provides[service])

                for module in modules_requiring:
                    try:
                        if provider_version in SpecifierSet(module.requires[service]):
                            valid_candidates.append(provider)
                    except InvalidSpecifier as e:
                        raise RuntimeError(f"Check requirements config for module {module.name}({module.id}): {e}") from e
            
            
            if not valid_candidates:
                raise RuntimeError(f"No compatible provider found for service '{service}'")

            # Highest priority first, then highest version.
            provider = max(valid_candidates, key=lambda module: (module.priority, Version(module.provides[service]),),)

            resolved_services[service] = provider

        return resolved_services
    

class LoadOrderResolver(Component):
    # def resolve(self, modules_by_id: dict[str, ModuleData]) -> list[ModuleData]:
    #     modules = modules_by_id

    #     providers: dict[str, list[ModuleData]] = defaultdict(list)

    #     for module in modules.values():
    #         for service in module.provides:
    #             providers[service].append(module)

    #     dependencies: dict[str, set[str]] = {module.id: set() for module in modules.values()}

    #     for module in modules.values():
    #         for service, specifier in module.requires.items():
    #             candidates = providers.get(service, [])

    #             if not candidates:
    #                 raise RuntimeError(f"Module '{module.name}' requires '{service}', but no provider was found.")

    #             try:
    #                 valid_candidates = [provider for provider in candidates if Version(provider.provides[service]) in SpecifierSet(specifier)]
    #             except InvalidSpecifier as e:
    #                 raise RuntimeError(f"Invalid requirement '{specifier}' in module '{module.name}' for service '{service}'.") from e

    #             if not valid_candidates:
    #                 raise RuntimeError(f"Module '{module.name}' requires '{service} {specifier}', but no compatible provider was found.")

    #             provider = max(valid_candidates, key=lambda m: (Version(m.version), m.priority))

    #             if provider.id == module.id:
    #                 raise RuntimeError(f"Module '{module.name}' cannot depend on itself.")

    #             dependencies[module.id].add(provider.id)

    #     # Copy used only by the topological sort.
    #     remaining_dependencies = {module_id: set(deps) for module_id, deps in dependencies.items()}

    #     load_order: list[ModuleData] = []
    #     queue = deque(
    #         module_id
    #         for module_id, deps in remaining_dependencies.items()
    #         if not deps
    #     )

    #     while queue:
    #         module_id = queue.popleft()
    #         load_order.append(modules[module_id])

    #         for dependent_id, deps in remaining_dependencies.items():
    #             if module_id in deps:
    #                 deps.remove(module_id)

    #                 if not deps:
    #                     queue.append(dependent_id)

    #     if len(load_order) != len(modules):
    #         remaining = [module_id for module_id, deps in remaining_dependencies.items() if deps]

    #         raise RuntimeError("Circular module dependency detected involving: " + ", ".join(remaining))

    #     return load_order
    
    def resolve(self, modules_by_id: dict[str, ModuleData]) -> list[ModuleData]:
        modules = modules_by_id
        print("modules", modules)

        print("\n=== DEPENDENCY RESOLUTION ===")
        print("Modules:", list(modules))

        providers: dict[str, list[ModuleData]] = defaultdict(list)

        for module in modules.values():
            for service in module.provides:
                providers[service].append(module)

        print("\nProviders:")
        for service, service_providers in providers.items():
            print(f"  {service}: {[module.id for module in service_providers]}")

        used_services = {service for module in modules.values() for service in module.requires}
        print("\nUsed services:", used_services)

        active: set[str] = {module.id for module in modules.values() if module.core_module}

        print("\nInitial active modules:", active)

        def get_provider(module: ModuleData, service: str, specifier: str) -> ModuleData | None:
            print(f"    Looking for provider of '{service} {specifier}' for '{module.id}'")

            try:
                candidates = [
                    provider
                    for provider in providers.get(service, [])
                    if Version(provider.provides[service]) in SpecifierSet(specifier)
                ]
            except InvalidSpecifier as e:
                print(f"    INVALID SPECIFIER: {specifier}")
                raise RuntimeError(
                    f"Invalid requirement '{specifier}' in module '{module.name}' for service '{service}'."
                ) from e

            print(f"    Compatible providers: {[provider.id for provider in candidates]}")

            if not candidates:
                print("    -> NO PROVIDER")
                return None

            provider = max(candidates, key=lambda m: (Version(m.provides[service]), m.priority))

            print(f"    -> Selected provider: {provider.id}")
            return provider

        changed = True
        iteration = 0

        while changed:
            iteration += 1
            changed = False

            print(f"\n--- ACTIVATION PASS {iteration} ---")
            print("Active before pass:", active)

            for module in modules.values():
                print(f"\nChecking module '{module.id}'")
                print(f"  Core: {module.core_module}")
                print(f"  Requires: {module.requires}")
                print(f"  Provides: {module.provides}")

                if module.id in active:
                    print("  -> Already active")
                    continue

                unresolved = []

                for service, specifier in module.requires.items():
                    provider = get_provider(module, service, specifier)

                    if provider is None:
                        unresolved.append((service, specifier))

                if not unresolved:
                    print("  -> ALL REQUIREMENTS RESOLVE")
                    print(f"  -> ACTIVATING '{module.id}'")
                    active.add(module.id)
                    changed = True
                else:
                    print(f"  -> UNRESOLVED: {unresolved}")

            print("\nActive after pass:", active)

        print("\n=== ACTIVATION COMPLETE ===")
        print("Active modules:", active)

        print("\nChecking unresolved modules...")

        for module in modules.values():
            if module.id in active:
                continue

            print(f"\nUnresolved module: '{module.id}'")

            if module.core_module:
                print("  -> CORE MODULE, ERROR")
                raise RuntimeError(f"Core module '{module.name}' has unresolvable requirements.")

            provided_is_used = any(service in used_services for service in module.provides)

            print(f"  Provided services: {module.provides}")
            print(f"  Provided service used: {provided_is_used}")

            if provided_is_used:
                print("  -> USED PROVIDER, ERROR")
                raise RuntimeError(
                    f"Module '{module.name}' has unresolvable requirements, "
                    f"but provides a service that is required by another module."
                )

            print("  -> UNUSED PROVIDER, IGNORING")

        print("\n=== BUILDING DEPENDENCY GRAPH ===")

        dependencies: dict[str, set[str]] = {module_id: set() for module_id in active}

        for module_id in active:
            module = modules[module_id]

            print(f"\nModule '{module_id}'")

            for service, specifier in module.requires.items():
                provider = get_provider(module, service, specifier)

                if provider is None:
                    raise RuntimeError(
                        f"Module '{module.name}' requires '{service} {specifier}', "
                        f"but no compatible provider was found."
                    )

                print(f"  {service} -> {provider.id}")

                if provider.id == module.id:
                    raise RuntimeError(f"Module '{module.name}' cannot depend on itself.")

                dependencies[module.id].add(provider.id)

        print("\nDependencies:")
        for module_id, deps in dependencies.items():
            print(f"  {module_id} -> {deps}")

        remaining = {module_id: set(deps) for module_id, deps in dependencies.items()}

        load_order: list[ModuleData] = []
        queue = deque(module_id for module_id, deps in remaining.items() if not deps)

        print("\nInitial queue:", list(queue))

        while queue:
            module_id = queue.popleft()
            print(f"Loading order: adding '{module_id}'")

            load_order.append(modules[module_id])

            for dependent_id, deps in remaining.items():
                if module_id in deps:
                    deps.remove(module_id)

                    if not deps:
                        print(f"  -> '{dependent_id}' is now ready")
                        queue.append(dependent_id)

        if len(load_order) != len(active):
            remaining_modules = [
                module_id for module_id, deps in remaining.items() if deps
            ]

            print("\nCYCLE DETECTED")
            print("Remaining:", remaining_modules)

            raise RuntimeError(
                "Circular module dependency detected involving: "
                + ", ".join(remaining_modules)
            )

        print("\n=== FINAL LOAD ORDER ===")
        print([module.id for module in load_order])

        return load_order