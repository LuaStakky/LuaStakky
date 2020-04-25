from .ConfigGenerators import LuaTableGenerator
from collections import OrderedDict
from random import choice
import string

_internal_api_key = ''.join(choice(string.ascii_letters+string.digits) for i in range(64))
_tarantool_admin_key = ''.join(choice(string.ascii_letters+string.digits) for i in range(64))


class LuaConfigModuleGenerator(LuaTableGenerator):
    def __init__(self, conf):
        super().__init__(conf, None)

    def analyse_config(self):
        super().analyse_config()

        self.add_param('InternalKey', _internal_api_key)
        self.add_param('Domain', self._conf['domain'])

        # Tarantool
        self.begin_section('Tarantool')
        self.add_param('AdminPassword', _tarantool_admin_key)
        self.add_param('Host', 'tarantool')
        self.add_param('Port', 3301)
        self.add_param('Timeout', 2000)
        self.end_section()

        def copy_from_yaml(subconf):
            for k, i in subconf.items():
                if isinstance(i, OrderedDict):
                    self.begin_section(k)
                    copy_from_yaml(i)
                    self.end_section()
                else:
                    self.add_param(k, i)

        copy_from_yaml(self._conf['LuaConfig'])


class LuaNginxConfigModuleGenerator(LuaConfigModuleGenerator):
    def analyse_config(self):
        super().analyse_config()
        
        self.add_param('WebDataDir', "/Site")

        cfg = self._conf["SMTP"]
        self.begin_section('SMTP')
        self.add_param('Email', cfg['Email'])
        self.add_param('User', cfg['User'])
        self.add_param('Domain', self._conf['domain'])
        self.add_param('Password', cfg['Password'])
        self.add_param('Server', cfg['Server'])
        self.add_param('Port', cfg['Port'])
        self.end_section()


class LuaTarantoolConfigModuleGenerator(LuaConfigModuleGenerator):
    def analyse_config(self):
        pass
