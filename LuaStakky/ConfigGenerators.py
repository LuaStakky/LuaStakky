from .FsController import StakkyBuildFile
from hiyapyco import dump as yaml_dump
from numbers import Number
from abc import ABC, abstractmethod
from .FsController import StakkyBuildFile
import string


# Config Generators

class ConfigGenerator(ABC):
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

    @abstractmethod
    def analise_config(self):
        pass

    @abstractmethod
    def render_config(self):
        pass


class LuaTableGenerator(ConfigGenerator, ABC):
    _out_config = ['return {']
    _tabs = 0

    def __init__(self, conf, subconf):
        super().__init__(conf, subconf)

    @staticmethod
    def _py_value_to_lua(data):
        if isinstance(data, str):
            if "'" in data or "\n" in data:
                return '[[' + data + ']]'
            else:
                return "'" + data + "'"
        elif isinstance(data, Number):
            return data
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

    def analise_config(self):
        if self._conf["stakky_debug"]:
            self._tabs = 1

    def render_config(self):
        return ('\n' if self._conf["stakky_debug"] else '').join(self._out_config + ['}'])


class DockerFileGenerator(ConfigGenerator, ABC):
    _out_config = []
    BASE_IMAGE = []
    _cmd = []
    _work_dir = ''

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
                         (['CMD ' + str(self._cmd)] if len(self._cmd) > 0 else []))


class YamlConfigGenerator(ConfigGenerator, ABC):
    _out_config = {}
    _curr_path = []
    _curr_subconf = {}

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
        last_el = self._curr_path.pop()
        path_end = self._out_config
        for i in self._curr_path:
            path_end = path_end[i]
        path_end[last_el] = self._curr_subconf
        self._curr_subconf = {}
        self._curr_path = []
        return yaml_dump(self._out_config, default_flow_style=True)


class YamlSubConfGenerator(YamlConfigGenerator, ABC):
    def render_config(self):
        super().render_config()
        return self._out_config


# ConfigGeneratorList & fs utils for it

class ConfigGenerators(dict):
    class StakkyConfigFile(StakkyBuildFile):
        def __init__(self, path, fs_profile_controller, config):
            super(ConfigGenerators.StakkyConfigFile, self).__init__(path, fs_profile_controller)
            self.config = config

        def build(self):
            with self.open('w') as f:
                self.config.analise_config()
                f.write(self.config.render_config())

    def __init__(self, fs):
        super(ConfigGenerators, self).__init__()
        self.fs = fs

    def add(self, path, val):
        self[path] = val

    def __setitem__(self, path, val):
        super(ConfigGenerators, self).__setitem__(path, self.StakkyConfigFile(self.fs.mk_build_file(path), self.fs, val))

    def build(self):
        for i in self.values():
            i.build()
