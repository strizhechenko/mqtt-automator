from aiomqtt import ProtocolVersion, Client


class Broker:  # pylint: disable=too-few-public-methods
    def __init__(self, ip: str, protocol: int = 5):
        self.ip = ip
        self.protocol = ProtocolVersion(protocol)

    def get_client(self):
        return Client(self.ip, protocol=self.protocol)
