from logger import app_logger as log
from architecture import Component, Module, ModuleMetadata
from ModuleManager import ModuleManager


class WindowsAppModule(Module):
    metadata = ModuleMetadata(
        name="windows_apps",
        version="1.0.0",
        provides=["app_provider"],
    )

    def on_load(self):
        print("WindowsAppModule loaded")


class PetModule(Module):
    metadata = ModuleMetadata(
        name="pet",
        version="1.0.0",
        requires=["app_provider"],
    )

    def on_load(self):
        app_module = self.services["app_provider"]

        print(
            "PetModule loaded, connected to:",
            app_module.metadata.name
        )