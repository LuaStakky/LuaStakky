from .FsController import FsController
from .Nginx import StakkyNginx
from .Tarantool import StakkyTarantool
from .AdminPanel import StakkyAdminPanel
from .Exeptions import *
from .BaseModule import StakkyContainerModule, StakkyModule
from .ConfigGenerators import DockerComposeConfigGenerator
from typing import Dict
import hiyapyco, os


class StakkyProfile:
    def __init__(self, name, path, confs, services_register, fs_controller):
        self.services: Dict[str, StakkyModule] = {}
        self.name = name
        self._services_register = services_register
        self.conf = hiyapyco.load([os.path.join(os.path.dirname(__file__), "default.yaml")] + confs,
                                  method=hiyapyco.METHOD_MERGE)
        self.fs = fs_controller.get_profile_controller(name)
        for k, curr_conf in self.conf["services"].items():
            if curr_conf:
                if "off" in curr_conf.keys():
                    if curr_conf["off"]:
                        continue
                self.services[k] = services_register[k](name, self.conf, curr_conf, self.fs)
        for i in self.services.values():
            for i0 in self.services.values():
                if id(i) != id(i0):
                    i.register_other_service(i0, i0.register_self_in_services(i))
        self._docker_compose_config_generator = None

    def build(self):
        for i in self.services.values():
            i.build()

        self._docker_compose_config_generator = DockerComposeConfigGenerator(self.conf)
        for i in self.services.values():
            if isinstance(i, StakkyContainerModule):
                for i0 in i.get_containers():
                    self._docker_compose_config_generator.add_service(i0)
        self._docker_compose_config_generator.analyse_config()

        with self.fs.mk_compose_file().open('w') as f:
            f.write(self._docker_compose_config_generator.render_config())


class StakkyApp:
    def __init__(self, path=None, conf=None):
        self._services_register = {}
        self.loaded_profiles = {}
        self._path = path
        self.init_modules_register()
        self._conf = conf
        self._main_config_name = self._find_config(conf if conf else 'stakky')
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
        self.register_service(StakkyAdminPanel)

    def get_profile(self, name='default'):
        if name not in self.loaded_profiles:
            second_conf = self._find_config((self._conf if self._conf else 'stakky') + '.' + name)
            if name != 'default' and not second_conf:
                raise EConfigNotFound()
            self.loaded_profiles[name] = StakkyProfile(name, self._path,
                                                       [self._main_config_name, second_conf] if second_conf else [
                                                           self._main_config_name],
                                                       self._services_register, self.fs)
        return self.loaded_profiles[name]

    def build(self, profile='default'):
        self.get_profile(profile).build()
