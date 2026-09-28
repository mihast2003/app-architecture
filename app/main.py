from logger import app_logger as log
from architecture import Component, Module, ModuleMetadata

from ModuleManager import ModuleManager
from test_modules import WindowsAppModule, PetModule


manager = ModuleManager()

# manager.register(WindowsAppModule())
# manager.register(PetModule())

manager.load_all()