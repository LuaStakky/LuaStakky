from LuaStakky.TarantoolAppBuilder import *
import os
import pytest


def test():
    sub_conf = {
        "worker_processes": 12,
        "worker_connections": 8192,
        "keepalive_timeout": 75,
        "main": "manifest.yaml",
        "mount_points": {"app": "TestTarantoolApp", "modules": ["TarantoolModules"]}
    }
    main_conf = {"stakky_debug": False, "debug": False, "services": {"Tarantool": sub_conf}}
    entry = TarantoolAppEntry(main_conf, sub_conf, os.path.join(os.path.dirname(__file__), "TestTarantoolApp"))
    entry.analyse_config()
    print(entry.render_config())
