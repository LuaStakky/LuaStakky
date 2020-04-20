from .FsController import FsController
from .Nginx import StakkyNginx
from .Tarantool import StakkyTarantool
from .Exeptions import *
# from luaparser import ast,printers
from hiyapyco import load as yaml_load
import os


class StakkyProfile:
    config = []
    services = {}
    fs = None

    def __init__(self, name, path, configs, services_register, fs_controller):
        self.name = name
        self._services_register = services_register
        self.config = yaml_load([os.path.join(os.path.dirname(__file__),"default.yaml")]+configs)
        self.fs = fs_controller.get_profile_controller(name)
        for k, curr_conf in self.config["services"].items():
            if curr_conf:
                if "off" in curr_conf.keys():
                    if curr_conf["off"]:
                        continue
                self.services[k] = services_register[k](name, self.config, curr_conf, self.fs)
        for i in self.services.values():
            i.register_self_in_services(self.services)

    def build(self):
        for i in self.services.values():
            i.build()


class StakkyApp:
    _services_register = {}
    loaded_profiles = {}

    def __init__(self, path=None, config=None):
        self._path = path
        self.init_modules_register()
        self._config = config
        self._main_config_name = self._find_config(config if config else 'stakky')
        self.fs = FsController(work_dir=path)
        if not self._main_config_name:
            raise EConfigNotFound()

    def _find_config(self, config):
        pconfig = os.path.join(self._path, config)
        for i in [config, config + '.yaml', config + '.yml', pconfig, pconfig + '.yaml', pconfig + '.yml']:
            if os.path.isfile(i):
                return i

    def register_service(self, service):
        self._services_register[service.NAME] = service

    def init_modules_register(self):
        self.register_service(StakkyNginx)
        self.register_service(StakkyTarantool)

    def get_profile(self, name='default'):
        if name not in self.loaded_profiles:
            second_conf = self._find_config((self._config if self._config else 'stakky') + '.' + name)
            if name != 'default' and not second_conf:
                raise EConfigNotFound()
            self.loaded_profiles[name] = StakkyProfile(name, self._path,
                                                       [self._main_config_name, second_conf] if second_conf else [
                                                           self._main_config_name],
                                                       self._services_register, self.fs)
        return self.loaded_profiles[name]

    def build(self, profile='default'):
        self.get_profile(profile).build()
