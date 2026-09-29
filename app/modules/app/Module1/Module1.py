from app.core.architecture import Component, Module

class ModuleOne(Module):
    def on_init(self) -> None:
        pass

    def on_load(self):
        print("ModuleOne loaded 1")