from .FsController import StakkyBuildFile, StakkyFile, FsProfileController
from numbers import Number
from abc import ABC, abstractmethod
import string, hiyapyco


# Config Generators

class ConfigGenerator(ABC):
    @abstractmethod
    def analyse_config(self):
        pass

    @abstractmethod
    def render_config(self):
        pass


class STDConfigGenerator(ConfigGenerator, ABC):
    def __init__(self, conf, subconf):
        self._conf = conf
        self._subconf = subconf

    @abstractmethod
    def add_param(self, data):
        pass

    @abstractmethod
    def begin_section(self, data):
        pass

    @abstractmethod
    def end_section(self):
        pass


class LuaTableGenerator(STDConfigGenerator, ABC):
    def __init__(self, conf, subconf):
        super().__init__(conf, subconf)
        self._out_config = ['return {']
        self._tabs = 0
        if self._conf["stakky_debug"]:
            self._tabs = 1

    @staticmethod
    def _py_value_to_lua(data):
        if isinstance(data, str):
            if "'" in data or "\n" in data:
                return '[[' + data + ']]'
            else:
                return "'" + data + "'"
        elif isinstance(data, Number):
            return str(data)
        else:
            raise Exception('unknown type')

    @staticmethod
    def _is_valid_var_name(name):
        if not name or name[0] in string.digits:
            return False
        for character in name:
            if character not in string.ascii_letters + '_' + string.digits:
                return False
        return True

    def add_list(self, name, data):
        if data is None:
            data = name
            name = ''
        else:
            if isinstance(name, str):
                if not self._is_valid_var_name(name):
                    if not "'" in name:
                        name = "['" + name + "']"
                    elif not '"' in name:
                        name = '["' + name + '"]'
            elif isinstance(name, Number):
                name = "[" + str(name) + "]"
            else:
                raise Exception('unknown type')
            name = name + '='

        data = '{' + ','.join(list(map(lambda x: self._py_value_to_lua(x), data))) + '}'
        self._out_config.append('\t' * self._tabs + name + data + ',')

    def add_param(self, name, data=None):
        if data is None:
            data = name
            name = ''
        else:
            if isinstance(name, str):
                if not self._is_valid_var_name(name):
                    if not "'" in name:
                        name = "['" + name + "']"
                    elif not '"' in name:
                        name = '["' + name + '"]'
            elif isinstance(name, Number):
                name = "[" + str(name) + "]"
            else:
                raise Exception('unknown type')
            name = name + '='

        if isinstance(data, str):
            if not "'" in data:
                data = "'" + data + "'"
            elif not '"' in data:
                data = '"' + data + '"'
        elif isinstance(data, Number):
            data = str(data)
        else:
            raise Exception('unknown type')
        self._out_config.append('\t' * self._tabs + name + data + ',')

    def add_val(self, name, data):
        self._out_config.append('\t' * self._tabs + name + '=' + data + ',')

    def begin_section(self, name):
        self._out_config.append('\t' * self._tabs + name + '={')
        if self._conf["stakky_debug"]:
            self._tabs = self._tabs + 1

    def end_section(self):
        if self._conf["stakky_debug"]:
            self._tabs = self._tabs - 1
        if self._out_config[-1][-1].endswith(','):
            self._out_config[-1] = self._out_config[-1][:-1]
        self._out_config.append(self._tabs * '\t' + '},')

    def render_config(self):
        return ('\n' if self._conf["stakky_debug"] else '').join(self._out_config + ['}'])


class DockerFileGenerator(STDConfigGenerator, ABC):
    BASE_IMAGE = []

    def __init__(self, conf, subconf):
        super().__init__(conf, subconf)
        self._out_config = []
        self._cmd = []
        self._work_dir = ''

    def add_param(self, data):
        self._out_config.append(' '.join(data))

    def set_cmd(self, data):
        self._cmd = data

    def set_work_dir(self, data):
        self._work_dir = data

    def add_run(self, data):
        self._out_config.append(' '.join(['RUN'] + data))

    def add_mount_point(self, host_path, guest_path):
        self._out_config.append('ADD ' + host_path + ' ' + guest_path)

    def begin_section(self, data):
        pass

    def end_section(self):
        pass

    def render_config(self):
        return '\n'.join(['FROM ' + self.BASE_IMAGE[0] + '/' + self.BASE_IMAGE[1] + ':' + (
            self.BASE_IMAGE[2] if len(self.BASE_IMAGE) > 2 else 'latest')] +
                         self._out_config +
                         (['WORKDIR ' + str(self._work_dir)] if len(self._work_dir) > 0 else []) +
                         (['CMD ' + str(self._cmd).replace("'", '"')] if len(self._cmd) > 0 else []))


class YamlConfigGenerator(STDConfigGenerator, ABC):
    def __init__(self, conf, subconf):
        super().__init__(conf, subconf)
        self._out_config = {}
        self._curr_path = []
        self._curr_subconf = {}

    def add_param(self, data):
        self._curr_subconf[data[0]] = data[1]

    def add_subconf(self, name, subconf):
        self._curr_subconf[name] = subconf.render_config()

    def begin_section(self, data):
        self._curr_subconf[data] = {}
        if len(self._curr_path) == 0:
            self._out_config = self._curr_subconf
        else:
            path_end = self._out_config
            for i in self._curr_path[:-1]:
                path_end = path_end[i]
            path_end[self._curr_path[-1]] = self._curr_subconf
        self._curr_subconf = {}
        self._curr_path.append(data)

    def end_section(self):
        last_el = self._curr_path.pop()
        path_end = self._out_config
        for i in self._curr_path:
            path_end = path_end[i]
        path_end[last_el] = self._curr_subconf
        self._curr_subconf = path_end

    def render_config(self):
        if len(self._curr_path) > 0:
            last_el = self._curr_path.pop()
            path_end = self._out_config
            for i in self._curr_path:
                path_end = path_end[i]
            path_end[last_el] = self._curr_subconf
        else:
            self._out_config = self._curr_subconf
        self._curr_subconf = {}
        self._curr_path = []
        return hiyapyco.dump(self._out_config, default_flow_style=not self._conf["debug"])


class YamlSubConfigGenerator(YamlConfigGenerator, ABC):
    def render_config(self):
        super().render_config()
        return self._out_config


class DockerComposeConfigPartGenerator(YamlSubConfigGenerator, ABC):
    service_name = ''

    def build_by_dockerfile(self, file: StakkyFile):
        self.begin_section('build')
        self.add_param(['context', '.'])
        self.add_param(['dockerfile', file.get_project_alias()])
        self.end_section()


class DockerComposeConfigGenerator(YamlConfigGenerator):
    def __init__(self, conf):
        super().__init__(conf, None)
        self.services = dict()

    def add_service(self, service: DockerComposeConfigPartGenerator):
        self.services[service.service_name] = service

    def analyse_config(self):
        self.add_param(['version', '3'])

        self.begin_section('services')
        for k, i in self.services.items():
            i.analyse_config()
            self.add_subconf(k, i)
        self.end_section()


# ConfigGeneratorList & fs utils for it

class ConfigGenerators(dict):
    class StakkyConfigFile(StakkyBuildFile):
        def __init__(self, path, fs_profile_controller, config):
            super(ConfigGenerators.StakkyConfigFile, self).__init__(path, fs_profile_controller)
            self.config = config

        def build(self):
            with self.open('w') as f:
                self.config.analyse_config()
                f.write(self.config.render_config())

    def __init__(self, fs: FsProfileController):
        super(ConfigGenerators, self).__init__()
        self.fs = fs

    def add(self, path, val: ConfigGenerator):
        self[path] = val

    def __setitem__(self, path, val: ConfigGenerator):
        super(ConfigGenerators, self).__setitem__(path,
                                                  self.StakkyConfigFile(self.fs.mk_build_filename(path), self.fs, val))

    def build(self):
        for i in self.values():
            i.build()
