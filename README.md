# LuaStakky
LuaStakky - full stack lua web framework

## What's under the hood?
+ Docker (docker-compose)
+ Openresty (Nginx with lua) with build-in modules:
    * lua-cmsgpack
    * etlua (lua-based template language)
    * inspect
    * lua-resty-http
    * lua-resty-cookie
+ Tarantool (DB) with 2 build modes:
    * Trivial app (as classic 1 main lua file+ lua modules)
    * Advanced app (custom build system with microservice architecture)
+ fengari (js lua implementation) *WIP*

## Installation

Install docker on your system before.

    pip3 install LuaStakky

## Some usefull examples

* [Example-Management](https://github.com/LuaStakky/Example-Management) and [GUI for it](https://github.com/LuaStakky/Example-Management-DesktopGUI).
  This example show advanced build system for tarantool.

## Official templates

* [LuaStakkyStaticSimpleAppTemplate](https://github.com/LuaStakky/LuaStakkyStaticSimpleAppTemplate)
* [LuaStakkyStaticTemplate](https://github.com/LuaStakky/LuaStakkyStaticTemplate)

## License
[MIT](https://choosealicense.com/licenses/mit/)
