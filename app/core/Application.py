from pathlib import Path

from app.core.logger import app_logger as log
from app.core.architecture import Component, Module

from app.core.ModuleManager import ModuleManager

ROOT_DIR = Path("D:\\work\\projects\\app-architecture")


class Application():
    def __init__(self) -> None:
        modules_dir = ROOT_DIR / "app" / "modules"

        self.module_manager = ModuleManager()

        # self.module_manager.load_core_modules(modules_dir)

        self.module_manager.discover_modules(modules_dir)
        self.module_manager.index_modules()

        self.module_manager.start_all()

        self.module_manager.load_all()

    def debug(self):
        print("debugging application")


