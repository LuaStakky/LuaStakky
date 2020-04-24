class ContainerController:
    def __init__(self, conf):
        self.compose = {}
        self.build = []
        self.conf = conf
