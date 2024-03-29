from .BaseModule import *
from .ConfigGenerators import STDConfigGenerator, DockerComposeConfigPartGenerator, DockerFileGenerator, \
    ConfigGenerators
from .Tarantool import StakkyTarantool
from .Utils import gen_lua_path_part
from os import path
from .LuaConfigModule import LuaNginxConfigModuleGenerator


class StakkyNginx(StakkyContainerModule):
    class NginxConfigGenerator(STDConfigGenerator):
        def __init__(self, conf, subconf):
            super().__init__(conf, subconf)
            self._out_config = []
            self._tabs = 0
            self._limits = {}
            self._LIMIT_TYPE_TO_NGINX_LIMIT_TYPE = {"ip": '$binary_remote_addr'}
            self.redirect_servers = []

        def add_param(self, data):
            self._out_config.append('\t' * self._tabs + ' '.join(map(str, data)) + ';')

        def begin_section(self, data):
            self._out_config.append('\t' * self._tabs + ' '.join(data) + '{')
            if self._conf["stakky_debug"]:
                self._tabs = self._tabs + 1

        def end_section(self):
            if self._conf["stakky_debug"]:
                self._tabs = self._tabs - 1
            self._out_config.append(self._tabs * '\t' + '}')

        def _parse_limit(self, limit, name):
            def mk_delay(d):
                return 'delay=' + str(d) if isinstance(d, int) and d != 0 else 'nodelay'

            def mk_burst(b):
                return 'burst=' + str(b) + ' ' if b != 0 else ''

            return ['limit_req_zone',
                    self._LIMIT_TYPE_TO_NGINX_LIMIT_TYPE[limit["type"] if "type" in limit else "ip"],
                    'zone=' + name + ':' + (limit["mem"] if "mem" in limit else "2m"),
                    'rate=' + str(limit["rps"] if "rps" in limit else 10) + 'r/s'], \
                   ['limit_req', 'zone=' + name,
                    (mk_burst(limit['burst']) if "burst" in limit else '20') +
                    (mk_delay(limit['delay']) if "burst" in limit and "delay" in limit else 'nodelay')]

        def _begin_server(self, http=True, https=False, force_domain=None, local=False):
            self.begin_section(['server'])
            if local:
                domain = 'nginx'
            else:
                if force_domain:
                    domain = force_domain
                else:
                    domain = self._conf['domain']
            if domain != '*':
                self.add_param(['server_name', domain])
            if http:
                self.add_param(['listen', 80])
            if https:
                self.add_param(['listen', 443, 'ssl'])

        def _mk_http_redirect_server(self):
            self._begin_server()
            self.add_param(['return', '301', 'https://$host$request_uri'])
            self.end_section()

        def _mk_redirect_server(self, server: StakkySubdomainContainerModule):
            container = server.get_containers()[0]
            if container:
                security = server.get_security()
                if 'allow_http' in security.keys():
                    http = security['allow_http']
                else:
                    http = False
                if 'allow_https' in security.keys():
                    https = security['allow_https']
                else:
                    https = True

                self._begin_server(http=http, https=https, force_domain=server.get_domain())

                if https:
                    self.add_param(['ssl_certificate', 'Certificates'])
                    self.add_param(['ssl_certificate_key', 'Certificates'])
                    self.add_param(['ssl_protocols', 'SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1', 'TLSv1.2'])
                    if 'ssl_session_cache' in security.keys():
                        self.add_param(['ssl_session_cache', 'shared:SSL:' + str(security['ssl_session_cache']) + 'm'])

                self.add_param(['resolver', '127.0.0.11', '8.8.8.8', 'ipv6=off'])
                self.add_param(['charset', 'utf-8'])

                self.begin_section(['location', '/'])

                access_control = server.get_access_control()
                if access_control:
                    self.add_param(
                        ['access_by_lua', "'" + access_control.replace('\\', '\\\\').replace("'", "\\'") + "'"])
                self.add_param(['access_log', 'off'])
                self.add_param(['proxy_pass', 'http://' + container.service_name + '/'])

                self.end_section()
                self.end_section()

        def _mk_cors(self, cors):
            def add_not_none(name_end, req_type):
                value = req_type[name_end]
                if value != 'none':
                    self.add_param(['add_header', "Access-Control-" + name_end, value])

            if cors['enable']:
                simple, preflighted = cors['simple'], cors['preflighted']
                two_if = not ((simple['Allow-Origin'] in {preflighted['Allow-Origin'], 'none'}) and
                              (simple['Expose-Headers'] in {preflighted['Expose-Headers'], 'none'}))
                if two_if:
                    self.begin_section(['if', "($request_method != 'OPTIONS')"])
                add_not_none('Allow-Origin', simple)
                add_not_none('Expose-Headers', simple)
                if two_if:
                    self.end_section()
                self.begin_section(['if', "($request_method = 'OPTIONS')"])
                if simple['Allow-Origin'] == 'none' or two_if:
                    add_not_none('Allow-Origin', preflighted)
                if simple['Expose-Headers'] == 'none' or two_if:
                    add_not_none('Expose-Headers', preflighted)
                add_not_none('Allow-Methods', preflighted)
                add_not_none('Allow-Headers', preflighted)
                add_not_none('Max-Age', preflighted)
                self.add_param(['add_header', "'Content-Type'", "'text/plain; charset=utf-8'"])
                self.add_param(['add_header', "'Content-Length'", 0])
                self.add_param(['return', 204])
                self.end_section()

        def _mk_main_server(self, http, https, local=False):
            if local:
                http = True
                https = False
            self._begin_server(http, https, local=local)
            if https:
                self.add_param(['ssl_certificate', 'Certificates'])
                self.add_param(['ssl_certificate_key', 'Certificates'])
                self.add_param(['ssl_protocols', 'SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1', 'TLSv1.2'])
                self.add_param(['ssl_session_cache',
                                'shared:SSL:' + str(self._subconf['security']['ssl_session_cache']) + 'm'])
            self.add_param(['resolver', '127.0.0.11', '8.8.8.8', 'ipv6=off'])
            self.add_param(['charset', 'utf-8'])

            self.begin_section(['location', '/'])

            if local:
                self.add_param(["access_by_lua",
                                "'if ngx.req.get_uri_args(0).Key==require(\"Config\").InternalKey then return end ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)'"])
            else:
                self.add_param(self._limits['/'])
                self.add_param(['limit_req_log_level', 'warn'])
                self.add_param(['limit_req_status', '429'])

                # CORS
                self._mk_cors(self._subconf['cors'])

                for k, i in self._limits.items():
                    if k != '/':
                        if not k.startswith('/api/'):
                            self.begin_section(['location', k])
                            self.add_param(i)
                            self.end_section()

                self.begin_section(['location', '/api/'])

                for k, i in self._limits.items():
                    if k != '/':
                        if k.startswith('/api/'):
                            self.begin_section(['location', k])
                            self.add_param(i)
                            self.end_section()

                self.add_param(['rewrite_by_lua', """'require("NginxTarantoolConnector")(ngx)'"""])
                self.add_param(['expires', 'off'])
                self.end_section()

            self.begin_section(['location', '/'])
            self.add_param(['root', "'/Site'"])
            if self._subconf['main'] != 'none':
                if self._conf["debug"]:
                    self.add_param(['lua_code_cache', 'off'])
                self.add_param(['rewrite_by_lua_file', '"' + path.join('/App', self._subconf['main']) + '"'])
            self.end_section()

            self.end_section()

            self.end_section()

        def _mk_servers(self):
            security = self._subconf["security"]
            can_ssl = security["ssl_certificates_file"] != "none" if security["allow_https"] else False
            need_http_redirect = can_ssl and not security["allow_http"]
            if need_http_redirect:
                self._mk_http_redirect_server()
            '''
                #server {
                    #listen 444 ssl;
                    #server_name         *;
                    #ssl_certificate     Certificates;
                    #ssl_certificate_key Certificates;
                    #ssl_protocols       SSLv2 SSLv3 TLSv1 TLSv1.1 TLSv1.2;
                    #ssl_session_cache shared:SSL:10m;

                    #location / {
                    #    access_by_lua '
                    #      local Session=require("resty.cookie"):new():get("Session")
                    #      if Session then
                    #        local Status,User=require("TarantoolApi").GetCurrUser({Session})
                    #        if Status==200 then
                    #          if User.IsAdmin then
                    #              return
                    #          end
                    #        end
                    #      end
                    #      ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
                    #    ';
                    #    access_log off;
                    #    proxy_pass http://admin-panel/;
                    #}
                #}
            '''
            self._mk_main_server(not need_http_redirect, can_ssl)
            if self._subconf['local_server'] and self._subconf['main']:
                self._mk_main_server(True, False, local=True)
            for i in self.redirect_servers:
                self._mk_redirect_server(i)

        def analyse_config(self):
            # main parameters
            self.add_param(["worker_processes", self._subconf["worker_processes"]])
            # error_log /var/log/nginx/error.log error;
            self.add_param(['error_log', '/usr/local/openresty/nginx/logs/error.log'])
            # error_log stderr error;

            self.add_param(['pid', '/usr/local/openresty/nginx/nginx.pid'])
            self.add_param(['daemon', 'off'])

            self.begin_section(['events'])
            self.add_param(['worker_connections', self._subconf["worker_connections"]])
            self.add_param(['use', "epoll"])
            self.end_section()

            # http
            self.begin_section(['http'])

            if self._subconf["simple_log"]:
                self.add_param(['log_format', 'main', """'$remote_addr [$time_local] "$request" '
                          '$status $body_bytes_sent "$http_referer" '"""])
                self.add_param(['access_log', '/usr/local/openresty/nginx/logs/access.log', 'main'])

            # ToDo decide whether it is necessary:
            '''
            ssl_session_cache shared:SSL:10m;
            ssl_session_timeout 10m;
            '''

            self.add_param(['include', '/usr/local/openresty/nginx/conf/mime.types'])
            self.add_param(['default_type', 'application/octet-stream'])

            self.add_param(['keepalive_timeout', self._subconf["keepalive_timeout"]])

            # ToDo decide whether it is necessary:
            '''
            sendfile on;
            # tcp_nopush     on;
            # aio            on;
            '''
            i0 = 0
            for k, i in self._subconf["limit_rps"].items():
                limit_init_str, self._limits[k] = self._parse_limit(i, 'limit' + str(i0))
                self.add_param(limit_init_str)
                i0 = i0 + 1

            lua_package_path = '"'
            if self._subconf['main'] != 'none':
                for i in self._subconf['mount_points']['modules']:
                    lua_package_path = lua_package_path + gen_lua_path_part(
                        '/modules' + i if i.startswith(path.sep) else '/modules/' + i)
            for i in ['/AutoGenModules', '/App', '/usr/share/lua/']:
                lua_package_path = lua_package_path + gen_lua_path_part(i)
            self.add_param(['lua_package_path', lua_package_path + ';"'])
            self.add_param(['lua_package_cpath', '"/usr/lib/lua/5.1/?.so;/usr/lib/lua/5.1/loadall.so;;"'])
            self.add_param(['lua_ssl_protocols', 'SSLv3', 'TLSv1', 'TLSv1.1', 'TLSv1.2', 'SSLv2'])
            self.add_param(['lua_ssl_verify_depth', 5])
            self.add_param(['lua_ssl_trusted_certificate', 'cacert.pem'])

            self.add_param(['gzip', 'on'])
            self.add_param(['gzip_buffers', 128, '16k'])
            self.add_param(['gzip_comp_level', 9])
            self.add_param(['gzip_min_length', 4096])
            self.add_param(['gzip_types', "'*'"])

            self._mk_servers()

            '''access_log /usr/local/openresty/nginx/logs/access.log;'''
            self.end_section()  # http

        def render_config(self):
            return ('\n' if self._conf["stakky_debug"] else '').join(self._out_config)

    class NginxDockerFileGenerator(DockerFileGenerator):
        BASE_IMAGE = ['openresty', 'openresty', 'alpine-fat']

        def __init__(self, conf, subconf):
            super().__init__(conf, subconf)
            self.mount_points = dict()

        def analyse_config(self):
            self.add_run(['apk', 'add', 'git'])
            for i in self._subconf['modules']['from_luarocks']:
                self.add_run(['luarocks', 'install', i])

            for k, i in self.mount_points.items():
                self.add_mount_point(k, i)

            self.set_work_dir('/Site')
            self.set_cmd(["openresty", "-c", "/etc/nginx/nginx.conf"])

    class NginxDockerComposeConfigGenerator(DockerComposeConfigPartGenerator):
        service_name = 'nginx'

        def __init__(self, conf, subconf, config_generators: ConfigGenerators, depends):
            super().__init__(conf, subconf)
            self._generators = config_generators
            self._depends = depends
            self.mount_points = {}

        def analyse_config(self):
            self.build_by_dockerfile(self._generators['DockerfileNginx'])
            if self._depends and len(self._depends) > 0:
                self.add_param(['depends_on', self._depends])

            self.add_param(['ports', [str(self._subconf["net"]["http_port"]) + ":80",
                                      str(self._subconf["net"]["https_port"]) + ":443"]])

            # depends_on: tarantool, admin-panel
            if self._depends and len(self._depends) > 0:
                self.add_param(['depends_on', self._depends])

            mounts = []
            for k, i in self.mount_points.items():
                mounts.append(('' if k.startswith(('/', './')) else './') + k + ':' + i)
            self.add_param(['volumes', mounts])

    priority = -1000
    NAME = "Nginx"

    def __init__(self, profile_name, conf, subconf, fs_controller):
        super().__init__(profile_name, conf, subconf, fs_controller)
        self.cacert_file = None
        self._depends = []
        self.auto_gen_modules_dir = self._fs_controller.mk_build_subdir('NginxAutoGenModules')
        self.config_generators = ConfigGenerators(fs_controller)
        self.config_generators.add(path.join(self.auto_gen_modules_dir.get_build_alias(), 'Config.lua'),
                                   LuaNginxConfigModuleGenerator(self._conf))
        self.config_generators.add('Nginx.conf', self.NginxConfigGenerator(self._conf, self._subconf))
        self.config_generators.add('DockerfileNginx', self.NginxDockerFileGenerator(self._conf, self._subconf))
        self._docker_compose_generator = self.NginxDockerComposeConfigGenerator(self._conf, self._subconf,
                                                                                self.config_generators,
                                                                                self._depends)

    def register_other_service(self, service, data):
        if isinstance(service, StakkyContainerModule):
            if isinstance(service, StakkySubdomainContainerModule):
                self.config_generators['Nginx.conf'].config.redirect_servers.append(service)
            if isinstance(service, StakkyTarantool):
                self.config_generators.add(
                    path.join(self.auto_gen_modules_dir.get_build_alias(), 'TarantoolApi_Calls.lua'),
                    service.config_generators['TarantoolEntry.lua'].config.get_open_call_list())
            for i in service.get_containers():
                self._depends.append(i.service_name)

    def mk_mount_points(self):
        result = {
            self.cacert_file.get_project_alias(): '/etc/nginx/cacert.pem',
            self.config_generators['Nginx.conf'].get_project_alias(): '/etc/nginx/nginx.conf',
            self.auto_gen_modules_dir.get_project_alias(): '/AutoGenModules',
            self._subconf['mount_points']['web_data']: '/Site'
        }
        if self._subconf['security']['allow_https'] and self._subconf['security']['ssl_certificates_file'] != 'none':
            result[self._subconf['security']['ssl_certificates_file']] = '/etc/nginx/Certificates'

        if self._subconf['main'] != 'none':
            result[self._subconf['mount_points']['app']] = '/App',
            for i in self._subconf['mount_points']['modules']:
                result[i] = '/modules' + i if i.startswith(path.sep) else '/modules/' + i

        self.config_generators['DockerfileNginx'].config.mount_points = result
        if self._conf['debug']:
            self._docker_compose_generator.mount_points = result

    def get_containers(self):
        return [self._docker_compose_generator]

    def build(self):
        print('installing libs...')
        self.cacert_file = self._fs_controller.download_file(self._subconf['security']['ssl_certs_repo'], 'cacert.pem')

        self._fs_controller.get_file_from_repo('Nginx/NginxTarantoolConnector.lua',
                                               path.join(self.auto_gen_modules_dir.get_build_alias(),
                                                         'NginxTarantoolConnector.lua'))
        self._fs_controller.get_file_from_repo('Nginx/TarantoolApi.lua',
                                               path.join(self.auto_gen_modules_dir.get_build_alias(),
                                                         'TarantoolApi.lua'))

        self.mk_mount_points()
        self.config_generators.build()
