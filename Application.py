from app.logger import app_logger as log
from app.architecture import Component, Module, ModuleMetadata

from app.core.ModuleManager import ModuleManager
from app.test_modules import WindowsAppModule, PetModule


class Application():
    def __init__(self) -> None:
        manager = ModuleManager()

        manager.load_all()

# manager.register(WindowsAppModule())
# manager.register(PetModule())

