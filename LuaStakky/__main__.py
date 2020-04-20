import LuaStakky,os

App=LuaStakky.StakkyApp(path=os.getcwd())
App.build()




'''
Module=['return {']
for i in ast.parse(open('src/TarantoolApp.lua','r').read()).body.body:
    if i.__class__ is ast.Function:
        Module.append("['"+i.name.id+"']={")
        if len(i.args)>0:
            for i0 in i.args:
                Module.append("'"+i0.id+"'")
                Module.append(',')
            Module[-1]='}'
        else:
            Module.append('}')
        Module.append(',')
Module[-1]='}'
open('OpenRestyModules/TarantoolApi_Calls.lua','w').write(''.join(Module))
open('WebData/lua/TarantoolApi_Calls.lua','w').write(''.join(Module))
'''
