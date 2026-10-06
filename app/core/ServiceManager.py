from app.core.architecture import Component, Module

class ServiceManager(Component):
    def on_init(self):
        self.services = {}

    def register_service(self, name: str, module):
        self.services[name] = module

    def get_service(self, name: str):
        return self.services[name]