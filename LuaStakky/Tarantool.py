from .BaseModule import StakkyContainerModule
from .TarantoolAppBuilder import TarantoolTrivialAppEntry, TarantoolAdvancedAppEntry
from .ConfigGenerators import DockerFileGenerator, ConfigGenerators
from os import path
from .LuaConfigModule import LuaTarantoolConfigModuleGenerator


class StakkyTarantool(StakkyContainerModule):
    class TarantoolDockerFileGenerator(DockerFileGenerator):
        BASE_IMAGE = ['tarantool', 'tarantool', '2.3']

        def __init__(self, conf, subconf):
            super().__init__(conf, subconf)
            self.mount_points = dict()

        def analyse_config(self):
            # for i in self._subconf['modules']['from_luarocks']:
            #    self.add_run(['luarocks', 'install', i])

            for k, i in self.mount_points.items():
                self.add_mount_point(k, i)

            self.set_cmd(["tarantool", "/opt/tarantool/app.lua"])

    NAME = "Tarantool"
    APP_BUILDERS = {
        "advanced" : TarantoolAdvancedAppEntry,
        "trivial": TarantoolTrivialAppEntry,
    }

    def __init__(self, profile_name, conf, subconf, fs_controller):
        self._docker_compose_generator = None
        super().__init__(profile_name, conf, subconf, fs_controller)
        self.auto_gen_modules_dir = self._fs_controller.mk_build_subdir('TarantoolAutoGenModules')
        self.config_generators = ConfigGenerators(fs_controller)
        self.config_generators.add(path.join(self.auto_gen_modules_dir.get_build_alias(), 'Conf.lua'), LuaTarantoolConfigModuleGenerator(self._conf))
        self.config_generators.add('TarantoolEntry.lua', self.APP_BUILDERS[subconf["apptype"]](
            self._conf, self._subconf, path.join(fs_controller.work_dir,subconf['mount_points']['app'])))
        self.config_generators.add('DockerfileTarantool', self.TarantoolDockerFileGenerator(self._conf, self._subconf))

    def mk_mount_points(self):
        result = {
            # self.cacert_file.get_project_alias(): '/etc/nginx/cacert.pem',
            #self.config_generators['TarantoolEntry.lua'].get_project_alias(): '/opt/tarantool/app.lua',
            self.auto_gen_modules_dir.get_project_alias(): '/opt/AutoGenModules',
            #self._subconf['mount_points']['app']: '/'
        }

        '''ADD src/Config.lua /opt/tarantool/Config.lua'''

        for i in self._subconf['mount_points']['modules']:
            result[i] = i if i.startswith(path.sep) else path.sep + i

        self.config_generators['DockerfileTarantool'].config.mount_points = result

    def render_docker_compose_config(self):
        pass

    def get_containers(self):
        #if not self._docker_compose_generator:
        #    self._docker_compose_generator = self.NginxDockerComposeConfigGenerator(self._conf, self._subconf,
        #                                                                            self.config_generators,
        #                                                                            self._depends)
        return []#[self._docker_compose_generator]

    def build(self):
        # print('installing libs...')
        # self.cacert_file = self._fs_controller.download_file(self._subconf['security']['ssl_certs_repo'], 'cacert.pem')

        # self._fs_controller.get_file_from_repo('Nginx/NginxTarantoolConnector.lua',
        #                                       path.join(self.auto_gen_modules_dir.get_build_alias(),
        #                                                 'NginxTarantoolConnector.lua'))
        # self._fs_controller.get_file_from_repo('Nginx/TarantoolApi.lua',
        #                                       path.join(self.auto_gen_modules_dir.get_build_alias(),
        #                                                 'TarantoolApi.lua'))

        self.mk_mount_points()
        self.config_generators.build()
