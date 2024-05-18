from aiomqtt import ProtocolVersion, Client
from pydantic import BaseModel


class Broker(BaseModel):
    ip: str
    protocol: ProtocolVersion

    def get_client(self):
        return Client(self.ip, protocol=self.protocol)
