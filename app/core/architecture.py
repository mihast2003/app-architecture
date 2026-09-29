from typing import final, Any
from dataclasses import dataclass, field

from app.core.logger import app_logger as log

class Component():
    """
    Component is a base building block class. Has parent and children connections to establish ownership.
    """
    def __init__(self, parent) -> None:
        """
        Creates a Component() class

        :param parent: parent Component. Components are automatically loaded and unloaded in order of ownership.
        """
        if parent is None:
            raise ValueError("Component requires a parent")
        
        if parent.children:
            parent.children.append(self)

        self.parent = parent
        self.children: list = []
        self.log_loading()
        
    def log_loading(self):
        object_class = "Component"
        if Module in self.__class__.__bases__:
            object_class = "Module"

        log.debug(f"{self.parent.__class__.__name__}: {object_class} loaded: {self.__class__.__name__}")
        print(f"{self.parent.__class__.__name__}: {object_class} loaded: {self.__class__.__name__}")

# region start(), load(), unload()
    @final
    def _init(self):
        self.on_init()

        for child in self.children:
            child._init()

    def on_init(self) -> None:
        """Triggered immediately when Component is initialising and is used to establish component connections"""
        pass


    @final
    def _load(self):
        self.on_load()

        for child in self.children:
            child._load()

    def on_load(self) -> None:
        """Triggered after Component is initialised and is ready to be used"""
        pass


    @final
    def _unload(self):
        for child in self.children:
            child._unload()

        self.on_unload()

    def on_unload(self) -> None:
        """Triggered when Component is unloaded"""
        pass

#endregion



class Module(Component):
    """
    Inherits from Component(). Has metadata and can own Components or other Modules
    """
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.metadata: dict
        self.services: dict[str, Any] = {}

    def connect(self, role: str, service: Any):
        self.services[role] = service


