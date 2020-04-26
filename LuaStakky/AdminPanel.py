from .BaseModule import StakkySubdomainContainerModule
from .ConfigGenerators import DockerComposeConfigPartGenerator


class StakkyAdminPanel(StakkySubdomainContainerModule):
    class AdminPanelDockerComposeConfigGenerator(DockerComposeConfigPartGenerator):
        service_name = 'admin-panel'

        def __init__(self, conf, subconf):
            super().__init__(conf, subconf)
            self.mount_points = {}

        def analyse_config(self):
            self.add_param(['image', 'artem3213212/tarantool-admin'])
            self.add_param(['depends_on', ['tarantool']])
            self.add_param(['restart', 'always'])

    NAME = "AdminPanel"

    def __init__(self, profile_name, conf, subconf, fs_controller):
        super().__init__(profile_name, conf, subconf, fs_controller)
        self._docker_compose_generator = self.AdminPanelDockerComposeConfigGenerator(conf, subconf)

    def get_containers(self):
        return [self._docker_compose_generator]

    def get_domain(self):
        return self._subconf['domain']

    def get_security(self):
        return self._subconf['security']

    def get_access_control(self):
        return '''local Session=require("resty.cookie"):new():get("Session")
                      if Session then
                        local Status,User=require("TarantoolApi").GetCurrUser({Session})
                        if Status==200 then
                          if User.IsAdmin then
                              return
                          end
                        end
                      end
                      ngx.exit(ngx.HTTP_NOT_FOUND)'''

    def build(self):
        pass
