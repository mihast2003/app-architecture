from architecture import Component, Module
from logger import app_logger as log


class Manager(Module):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        component_1 = Component(self)
        component_2 = Component(self)
    


main_module = Manager(None)