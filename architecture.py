from logger import app_logger as log

class Component():
    def __init__(self, parent) -> None:
        self.children: list[Component] = []
        self.log_loading()
        
    def log_loading(self):
        object_class = "Component"
        if Module in self.__class__.__bases__:
            object_class = "Module"

        log.debug(f"{object_class} loaded: {self.__class__.__name__}")
        print(f"{object_class} loaded: {self.__class__.__name__}")

    def load(self):
        pass

    def unload(self):
        for child in self.children:
            child.unload()


class Module(Component):
    def __init__(self, parent) -> None:
        super().__init__(parent)



