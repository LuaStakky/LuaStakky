import LuaStakky, os, sys
from argparse import ArgumentParser

App = LuaStakky.StakkyApp(path=os.getcwd())
parser = ArgumentParser()
parser.add_argument('-P', '--profile')
args = parser.parse_args()
if args.profile:
    App.build(profile=args.profile)
else:
    App.build()
