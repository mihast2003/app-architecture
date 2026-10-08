from app.core.architecture import Component, Module

class FabricModule(Module):
    def on_init(self) -> None:
        pass

    def on_load(self):
        print("ShopModule loaded 1") 