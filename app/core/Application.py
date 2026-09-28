from logger import app_logger as log
from architecture import Component, Module, ModuleMetadata

from ModuleManager import ModuleManager
from test_modules import WindowsAppModule, PetModule


class Application():
    def __init__(self) -> None:
        manager = ModuleManager()

        manager.load_all()

# manager.register(WindowsAppModule())
# manager.register(PetModule())

