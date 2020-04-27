from abc import ABC, abstractmethod
from .ConfigGenerators import ConfigGenerator, LuaTableGenerator
from hiyapyco import load as yaml_load
import os
from typing import List, Dict
from luaparser import ast
from .Utils import gen_lua_path_part


def find_lua_global_functions(file):
    for i in ast.parse(file).body.body:
        if i.__class__ is ast.Function:
            name = i.name.id
            params = []
            if len(i.args) > 0:
                for i0 in i.args:
                    params.append(i0.id)
            yield name, params


class TarantoolAppEntry(ConfigGenerator, ABC):
    class CallListGenerator(LuaTableGenerator):
        def __init__(self, conf):
            super().__init__(conf, None)
            self.call_list: Dict[str, List[str]] = {}

        def analyse_config(self):
            super().analyse_config()

            for k, i in self.call_list.items():
                self.add_list(k, i)

        def add_call(self, name, data):
            self.call_list[name] = data

    def __init__(self, conf, subconf, folder):
        self._pre_config = []
        self._conf = conf
        self._subconf = subconf
        self._folder = folder

    def analyse_config(self):
        lua_path = gen_lua_path_part('/opt/tarantool')+gen_lua_path_part('/opt/AutoGenModules')
        for i in self._subconf["mount_points"]["modules"]:
            lua_path = lua_path + gen_lua_path_part(
                '/modules' + i if i.startswith(os.path.sep) else '/modules/' + i)
        self._pre_config.append("package.path='" + lua_path + ";'")
        self._pre_config.append("box.cfg{")
        self._pre_config.append("    listen = 3301,")
        self._pre_config.append("    work_dir = '/var/lib/tarantool',")
        self._pre_config.append("    wal_dir = 'WAL',")
        self._pre_config.append("    memtx_dir = 'MemTX',")
        self._pre_config.append("    vinyl_dir = 'Vinyl'")
        self._pre_config.append("}")

        self._pre_config.append("box.schema.user.passwd(require('Config').Tarantool.AdminPassword)")

        self._pre_config.append("require('console').listen('/var/lib/tarantool/admin.sock')")

    @abstractmethod
    def get_open_call_list(self):
        pass

    @abstractmethod
    def get_close_call_list(self):
        pass

class TarantoolTrivialAppEntry(TarantoolAppEntry):
    def __init__(self, conf, subconf, folder):
        super().__init__(conf, subconf, folder)
        self._calls = self.CallListGenerator(conf)
        self.file = open(os.path.join(folder, subconf["main"]), 'r').read()

    def analyse_config(self):
        super().analyse_config()
        for name, data in find_lua_global_functions(self.file):
            self._calls.add_call(name, data)

    def get_open_call_list(self):
        return self._calls

    def get_close_call_list(self):
        return self._calls

    def render_config(self):
        return '\n'.join(self._pre_config + [self.file])


class TarantoolAdvancedAppEntry(TarantoolAppEntry):
    class TarantoolAppUnit(ConfigGenerator):
        def __init__(self, conf, subconf, unit_conf, folder, open_calls, close_calls):
            self._conf = conf
            self._subconf = subconf
            self._unit_conf = unit_conf
            self._folder = folder
            self._out_config = []
            self.open_calls, self.close_calls = open_calls, close_calls

        def analyse_config(self):
            for k, i in self._unit_conf["imports"].items():
                self._out_config.append("unit=setmetatable({},{__index=global})")
                all_files = []
                for i0 in i["files"]:
                    if i0.endswith('/'):
                        files = []
                        for r, d, f in os.walk(os.path.join(self._folder, i0[:-1])):
                            for file in f:
                                files.append(os.path.join(r, file))
                        files.sort()
                        all_files = all_files + files
                    else:
                        all_files.append(os.path.join(self._folder, i0))

                # iproto_visible: "none" # all, none or username (guest equal all)
                # globals_visible: "global" # file, unit, global

                if i["iproto_visible"] == "none":
                    call_lists = []
                elif i["tarantool_user"] in ["guest", "all"]:
                    call_lists = [self.open_calls, self.close_calls]
                else:
                    call_lists = [self.close_calls]

                for i0 in all_files:
                    if i["globals_visible"] == 'global':
                        self._out_config.append('getmetatable(unit).__newindex = function(self, key, value)')
                        self._out_config.append('    global[key]=value')
                        self._out_config.append('end')
                        env_name = "global"
                    elif i["globals_visible"] == 'unit':
                        env_name = "unit"
                    else:
                        self._out_config.append('''file=setmetatable({},{__index=unit})''')
                        env_name = "file"

                    file = open(i0, 'r').read()
                    i1 = 0
                    while file.find(']' + '=' * i1 + ']') != -1:
                        i1 = i1 + 1

                    self._out_config.append('f=loadstring([' + '=' * i1 + '[' + file + ']' + '=' * i1 + '])')
                    self._out_config.append('setfenv(f, ' + env_name + ')()')

                    for name, params in find_lua_global_functions(file):
                        for call_list in call_lists:
                            call_list.add_call(name, params)
                        self._out_config.append('AddFunction(' + name + ', ' + env_name + '.' + name + ', ' +
                                                ('true' if i["iproto_visible"] in ["guest", "all"] else 'false') + ')')

                    if i["globals_visible"] == 'global':
                        self._out_config.append('''getmetatable(unit).__newindex=nil''')

        def render_config(self):
            return '\n'.join(self._out_config)

    def __init__(self, conf, subconf, folder):
        super().__init__(conf, subconf, folder)
        self.open_calls = self.CallListGenerator(conf)
        self.close_calls = self.CallListGenerator(conf)
        self._post_config = []
        self.units: List[TarantoolAdvancedAppEntry.TarantoolAppUnit] = []
        self._manifest = yaml_load(os.path.join(folder, subconf["main"]))
        for k, i in self._manifest["units"].items():
            unit_folder = os.path.join(folder, k)
            self.units.append(self.TarantoolAppUnit(conf, subconf, yaml_load([
                os.path.join(unit_folder, i["sub_manifest"])]) if i.get("sub_manifest", False) else i, unit_folder,
                                                    self.open_calls, self.close_calls))

    def analyse_config(self):
        super().analyse_config()
        self._pre_config.append("box.space._func:truncate()")

        self._pre_config.append("local function AddFunction(Name, Function, allow_guest)")
        self._pre_config.append("    _G[Name]=Function")
        self._pre_config.append("    if allow_guest then")
        self._pre_config.append("        box.schema.user.grant('', 'execute', 'function', Name, {if_not_exists=true})")
        self._pre_config.append("    else")
        self._pre_config.append("        box.schema.user.revoke('', 'execute', 'function', Name, {if_not_exists=true})")
        self._pre_config.append("    end")
        self._pre_config.append("end")

        # init env
        self._pre_config.append("local file, unit, global")
        self._pre_config.append("global={}")

        for i in self.units:
            i.analyse_config()

    def get_open_call_list(self):
        return self.open_calls

    def get_close_call_list(self):
        return self.close_calls

    def render_config(self):
        return '\n'.join(self._pre_config+[i.render_config() for i in self.units]+self._post_config)
