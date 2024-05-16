from aiomqtt import ProtocolVersion, Client


class Broker:
    def __init__(self, ip: str, proto: int = 5):
        self.ip = ip
        self.proto = ProtocolVersion(proto)

    def get_client(self):
        return Client(self.ip, protocol=self.proto)
