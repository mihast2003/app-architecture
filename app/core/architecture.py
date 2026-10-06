from typing import final, Any
from dataclasses import dataclass, field

from app.core.logger import app_logger as log

class Component():
    """
    Component is a base building block class. Has parent and children connections to establish ownership
    """
    def __init__(self, parent) -> None:
        """
        Creates a Component() class

        :param parent: parent Component. Components are automatically loaded and unloaded in order of ownership
        """
        if not isinstance(parent, (Component, Module)):
            print(parent.__class__.__bases__)
            raise ValueError(f"Component {self.__class__.__name__} requires a valid Component or Module parent")
        
        self.parent = parent
        self.children: list[Component] = []

        self.parent.children.append(self)

        self._init()

        self.log_loading()

    def detach(self):
        """
        Removes reference to Component from its parent's children, and the same for its children
        """
        for child in self.children.copy():
            child.detach()

        self.children.clear()
        if not self.parent: return

        try:
            self.parent.children.remove(self)
        except ValueError as e:
            raise RuntimeError(f"Could not remove a child Component: {e}") from e
        
        self.parent = None

        
    def log_loading(self):
        object_class = "Component"
        if isinstance(self, Module):
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

    def connect(self, service: str, module: Module):
        self.services[service] = module
        print(f"connected module {module.__class__.__name__} as service {service}")


