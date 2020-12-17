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
+ Tarantool (DB)
    * Trivial app (as classic 1 main lua file+ lua modules)
    * Advanced app (custom build system with microservice architecture)
+ fengari (js lua implementation) *WIP*

## License
[MIT](https://choosealicense.com/licenses/mit/)
