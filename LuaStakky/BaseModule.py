class StakkyModule:
    NAME = ""

    def __init__(self,profile_name , conf, subconf, fs_controller):
        self._profile_name=profile_name
        self._conf = conf
        self._subconf = subconf
        self._fs_controller = fs_controller

    def build(self):
        pass

    def register_self_in_services(self, services):
        pass

    def register_other_service(self, service, data):
        pass


class StakkyContainerModule(StakkyModule):
    def get_containers(self):
        return []
