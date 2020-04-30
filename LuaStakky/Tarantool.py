from .BaseModule import StakkyContainerModule
from .TarantoolAppBuilder import TarantoolTrivialAppEntry, TarantoolAdvancedAppEntry
from .ConfigGenerators import DockerFileGenerator, ConfigGenerators, DockerComposeConfigPartGenerator
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

            self.set_cmd('tarantool /opt/tarantool/app.lua')

    class TarantoolDockerComposeConfigGenerator(DockerComposeConfigPartGenerator):
        service_name = 'tarantool'

        def __init__(self, conf, subconf, config_generators: ConfigGenerators):
            super().__init__(conf, subconf)
            self._generators = config_generators
            self.mount_points = {}

        def analyse_config(self):
            self.build_by_dockerfile(self._generators['DockerfileTarantool'])

            self.add_param(['ports', [str(self._subconf["net"]["iproto_port"]) + ":3301"]])
            # depends_on: tarantool, admin-panel

            mounts = ['./DB:/var/lib/tarantool']
            for k, i in self.mount_points.items():
                mounts.append(('' if k.startswith(('/', './')) else './')+k+':'+i)
            self.add_param(['volumes', mounts])

    NAME = "Tarantool"
    APP_BUILDERS = {
        "advanced": TarantoolAdvancedAppEntry,
        "trivial": TarantoolTrivialAppEntry,
    }

    def __init__(self, profile_name, conf, subconf, fs_controller):
        super().__init__(profile_name, conf, subconf, fs_controller)
        self.auto_gen_modules_dir = self._fs_controller.mk_build_subdir('TarantoolAutoGenModules')

        self.config_generators = ConfigGenerators(fs_controller)
        self.config_generators.add(path.join(self.auto_gen_modules_dir.get_build_alias(), 'Config.lua'),
                                   LuaTarantoolConfigModuleGenerator(self._conf))

        self.config_generators.add('TarantoolEntry.lua', self.APP_BUILDERS[subconf["apptype"]](
            self._conf, self._subconf, path.join(fs_controller.work_dir, subconf['mount_points']['app'])))

        self.config_generators.add('DockerfileTarantool', self.TarantoolDockerFileGenerator(self._conf, self._subconf))
        self._docker_compose_generator = self.TarantoolDockerComposeConfigGenerator(self._conf, self._subconf,
                                                                                    self.config_generators)

    def mk_mount_points(self):
        result = {
            # self.cacert_file.get_project_alias(): '/etc/nginx/cacert.pem',
            self.config_generators['TarantoolEntry.lua'].get_project_alias(): '/opt/tarantool/app.lua',
            self.auto_gen_modules_dir.get_project_alias(): '/opt/AutoGenModules',
        }

        '''ADD src/Config.lua /opt/tarantool/Config.lua'''

        for i in self._subconf['mount_points']['modules']:
            result[i] = '/modules' + i if i.startswith(path.sep) else '/modules/' + i

        self.config_generators['DockerfileTarantool'].config.mount_points = result
        if self._conf['debug']:
            self._docker_compose_generator.mount_points = result

    def get_containers(self):
        return [self._docker_compose_generator]

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
