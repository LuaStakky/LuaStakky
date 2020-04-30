from abc import ABC, abstractmethod
from typing import List
from .ConfigGenerators import DockerComposeConfigPartGenerator


class StakkyModule(ABC):
    priority = 0
    NAME = ""

    def __init__(self, profile_name, conf, subconf, fs_controller):
        self._profile_name = profile_name
        self._conf = conf
        self._subconf = subconf
        self._fs_controller = fs_controller

    @abstractmethod
    def build(self):
        pass

    def register_self_in_services(self, services):
        pass

    def register_other_service(self, service, data):  # data getting from register_self_in_services
        pass


class StakkyContainerModule(StakkyModule, ABC):
    @abstractmethod
    def get_containers(self) -> List[DockerComposeConfigPartGenerator]:
        pass


class StakkySubdomainContainerModule(StakkyContainerModule, ABC):
    @abstractmethod
    def get_domain(self):
        pass

    @abstractmethod
    def get_security(self):
        pass

    def get_access_control(self):
        return None
