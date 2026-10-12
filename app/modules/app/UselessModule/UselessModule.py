from app.core.architecture import Component, Module

class UselessModule(Module):
    def on_init(self) -> None:
        pass

    def on_load(self):
        pass