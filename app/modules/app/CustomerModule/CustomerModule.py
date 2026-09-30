from app.core.architecture import Component, Module

class CustomerModule(Module):
    def on_init(self) -> None:
        pass

    def on_load(self):
        print("CustomerModule loaded 1")