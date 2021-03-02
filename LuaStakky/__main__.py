import LuaStakky, os, sys
from argparse import ArgumentParser

def entry():
    App = LuaStakky.StakkyApp(path=os.getcwd())
    parser = ArgumentParser()
    parser.add_argument('-P', '--profile')
    args = parser.parse_args()
    if args.profile:
        App.build(profile=args.profile)
    else:
        App.build()

if __name__=="__main__":
    entry()