from typing import final, Any
from dataclasses import dataclass, field

from logger import app_logger as log

@dataclass
class ModuleMetadata:
    name: str
    version: str
    role: str
    provides: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)

class Component():
    """
    Component is a base building block class
    """
    def __init__(self, parent) -> None:
        """
        Creates a Component() class

        :param parent: parent Component. Components are automatically loaded and unloaded in order of ownership.
        """
        self.children: list = []
        self.log_loading()
        
    def log_loading(self):
        object_class = "Component"
        if Module in self.__class__.__bases__:
            object_class = "Module"

        log.debug(f"{object_class} loaded: {self.__class__.__name__}")
        print(f"{object_class} loaded: {self.__class__.__name__}")

# region start, load, unload
    @final
    def start(self):
        self.on_load()

        for child in self.children:
            child.start()

    def on_start(self) -> None:
        """Triggered immediately when Component is initialising and is used to establish component connections"""
        pass


    @final
    def load(self):
        self.on_load()

        for child in self.children:
            child.load()

    def on_load(self) -> None:
        """Triggered after Component is initialised and is ready to be used"""
        pass


    @final
    def unload(self):
        for child in self.children:
            child.unload()

        self.on_unload()

    def on_unload(self) -> None:
        """Triggered when Component is unloaded"""
        pass

#endregion


class Module(Component):
    """
    Docstring for Module
    """
    metadata: ModuleMetadata

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.metadata: ModuleMetadata
        self.services: dict[str, Any] = {}

    def connect(self, role: str, service: Any):
        self.services[role] = service


