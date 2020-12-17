from abc import ABC, abstractmethod
from .ConfigGenerators import ConfigGenerator, LuaTableGenerator
from hiyapyco import load as yaml_load
import os
from typing import List, Dict
from luaparser import ast
from .Utils import gen_lua_path_part
from .Exeptions import ETarantoolAdvancedAppLoopInRequirements


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
            print(self.call_list)
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
        lua_path = gen_lua_path_part('/opt/tarantool') + gen_lua_path_part('/opt/AutoGenModules')
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
        def __init__(self, conf, subconf, appconf, unit_conf, folder, open_calls, close_calls):
            self._conf = conf
            self._appconf = appconf
            self._subconf = subconf
            self._unit_conf = unit_conf
            self._folder = folder
            self._out_config = []
            self.open_calls, self.close_calls = open_calls, close_calls
            self.requirements = unit_conf['requirements'] if unit_conf.get("requirements", False) else []

        def analyse_config(self):
            self._out_config.append("do")
            self._out_config.append("local NeedAppendToGlobal={}")
            self._out_config.append("local UnitEnv=GlobalEnv")

            for k, i in self._unit_conf["imports"].items():
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

                preloaded_data = i.get("preloaded_data", None)
                if preloaded_data:
                    self._out_config.append('local preloaded_data={')
                    for var_name, var_data in preloaded_data.items():
                        if var_data['type'] == 'file':
                            with open(os.path.join(self._folder, var_data['file']), 'r') as f:
                                text = f.read()
                            i1 = 0
                            while text.find(']' + '=' * i1 + ']') != -1:
                                i1 = i1 + 1
                            self._out_config.append(var_name + '=[' + '=' * i1 + '[' + text + ']' + '=' * i1 + '],')
                    self._out_config.append('}')
                else:
                    self._out_config.append('local preloaded_data=nil')

                iproto_visible = i.get("iproto_visible", 'none')
                iproto_prefix = i.get("iproto_prefix", '')
                globals_visible = i.get("globals_visible", 'file')

                for i0 in all_files:
                    self._out_config.append("local NewEnv={}")
                    self._out_config.append("setmetatable(NewEnv,{__index=UnitEnv})")

                    file = open(i0, 'r').read()
                    i1 = 0
                    while file.find(']' + '=' * i1 + ']') != -1:
                        i1 = i1 + 1

                    self._out_config.append('NewEnv.preloaded_data=preloaded_data')

                    self._out_config.append('local f=loadstring([' + '=' * i1 + '[' + file + ']' + '=' * i1 + '],[['+i0[self._folder.rfind(os.path.sep)+1:]+']])')
                    self._out_config.append('setfenv(f, NewEnv)')
                    self._out_config.append("f()")

                    if globals_visible != 'file':
                        self._out_config.append("UnitEnv=NewEnv")
                    if globals_visible == 'global':
                        self._out_config.append("NeedAppendToGlobal[#NeedAppendToGlobal+1]=NewEnv")

                    for name, params in find_lua_global_functions(file):
                        self._out_config.append('setfenv(NewEnv[ [[' + name + ']] ],NewEnv)')
                        if iproto_visible != 'none':
                            iproto_name = iproto_prefix + name
                            self.close_calls.add_call(iproto_name, params)
                            if iproto_visible == 'all':
                                self.open_calls.add_call(iproto_name, params)
                            self._out_config.append(
                                'AddFunction([[' + iproto_name + ']], NewEnv[ [[' + name + ']] ], ' +
                                ('true' if iproto_visible == "all" else 'false') + ', NewEnv)')
            self._out_config.append("for _,i in pairs(NeedAppendToGlobal) do")
            self._out_config.append("local NewEnv=CopyTable(i)")
            self._out_config.append("setmetatable(NewEnv,{__index=GlobalEnv})")
            self._out_config.append("GlobalEnv=NewEnv")
            self._out_config.append("end")
            self._out_config.append("end")

        def render_config(self):
            return '\n'.join(self._out_config)

    def __init__(self, conf, subconf, folder):
        super().__init__(conf, subconf, folder)
        self._open_calls = self.CallListGenerator(conf)
        self._close_calls = self.CallListGenerator(conf)
        self._post_config = []
        units: Dict[TarantoolAdvancedAppEntry.TarantoolAppUnit] = {}
        self._manifest = yaml_load(os.path.join(folder, subconf["main"]))
        for k, i in self._manifest["units"].items():
            unit_folder = os.path.join(folder, k)
            units[k] = self.TarantoolAppUnit(conf, subconf, self._manifest, yaml_load([
                os.path.join(unit_folder, i["sub_manifest"])]) if i.get("sub_manifest", False) else i, unit_folder,
                                             self._open_calls, self._close_calls)
        # Topological Sorting(Tarjan algo)
        self.units: List[TarantoolAdvancedAppEntry.TarantoolAppUnit] = []
        stack = []
        unprocessed = set(units.keys())

        def recur(unit_name):
            if unit_name in stack:
                raise ETarantoolAdvancedAppLoopInRequirements()
            stack.append(unit_name)
            for un in units[unit_name].requirements:
                if un in unprocessed:
                    recur(un)
            stack.pop()
            self.units.append(units[unit_name])
            unprocessed.remove(unit_name)

        while len(unprocessed) > 0:
            recur(next(iter(unprocessed)))

    def analyse_config(self):
        super().analyse_config()
        # self._pre_config.append("box.space._func:truncate()")

        self._pre_config.append('for _,i in box.space._func:pairs() do')
        self._pre_config.append("  if i[5]=='LUA' then")
        self._pre_config.append('    box.schema.func.drop(i[3],{if_exists=true})')
        self._pre_config.append('  end')
        self._pre_config.append('end')

        self._pre_config.append("local function CopyTable(table)")
        self._pre_config.append("    local Result={}")
        self._pre_config.append("    for k,v in pairs(table) do")
        self._pre_config.append("        Result[k]=v")
        self._pre_config.append("    end")
        self._pre_config.append("    return Result")
        self._pre_config.append("end")

        self._pre_config.append("local function AddFunction(Name, Function, allow_guest, Env)")
        self._pre_config.append("    _G[Name]=Function")
        self._pre_config.append("    box.schema.func.create(Name)")
        self._pre_config.append("    if allow_guest then")
        self._pre_config.append(
            "        box.schema.user.grant('guest', 'execute', 'function', Name, {if_not_exists=true})")
        self._pre_config.append(
            "        box.schema.user.grant('admin', 'execute', 'function', Name, {if_not_exists=true})")
        self._pre_config.append("    else")
        self._pre_config.append(
            "        box.schema.user.revoke('guest', 'execute', 'function', Name, {if_not_exists=true})")
        self._pre_config.append(
            "        box.schema.user.grant('admin', 'execute', 'function', Name, {if_not_exists=true})")
        self._pre_config.append("    end")
        self._pre_config.append("end")

        # init env
        self._pre_config.append("local GlobalEnv={}")
        self._pre_config.append("setmetatable(GlobalEnv,{__index=_G})")

        for i in self.units:
            i.analyse_config()

    def get_open_call_list(self):
        return self._open_calls

    def get_close_call_list(self):
        return self._close_calls

    def render_config(self):
        return '\n'.join(self._pre_config + [i.render_config() for i in self.units] + self._post_config)
