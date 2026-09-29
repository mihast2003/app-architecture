from app.core.logger import app_logger as log
from app.core.architecture import Component, Module

from app.core.ModuleManager import ModuleManager

from app.core.application import Application


app = Application()

app.debug()
