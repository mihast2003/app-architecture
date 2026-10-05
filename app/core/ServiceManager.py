from app.core.architecture import Component, Module

class ServiceManager(Component):
    def on_init(self):
        self.services = {}

    def register(self, name: str, module):
        self.services[name] = module

    def get(self, name: str):
        return self.services[name]