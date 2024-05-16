import asyncio
import json
import logging

from application.broker import Broker
from application.devices.base import BaseClient

log = logging.getLogger(__name__)


class YeelinkClient(BaseClient):
    def __init__(self, device_id: str, device_name: str, broker: Broker = None):
        super().__init__(device_id, device_name, broker)
        self.message_id = 0

    def subscriptions(self):
        """ На лампы не подписываемся, там вообще MQTT нет, надо только выключить их в 23:00"""
        return ()

    async def publish(self, sub_topic: str, payload):
        """Если устройство выключено - ничего страшного, сохраним _желаемое_ состояние и не будем его долбить"""
        if self.state.get(sub_topic) == payload:
            log.debug("Skipped because state-match %s", self.state)
            return

        self.message_id = ((self.message_id + 1) % 65000) + 1
        self.state[sub_topic] = payload
        try:
            reader, writer = await asyncio.open_connection(self.device_id, 55443)
        except OSError:
            log.warning("Can't connect to %s", self)
            return
        writer.write(
            (
                    json.dumps({
                        "id": self.message_id,
                        "method": sub_topic,
                        "params": ['on', 'smooth', 500] if payload else ['off']
                    })
                    + '\r\n'
            ).encode()
        )
        await writer.drain()
        log.info("Published %s %s %s", self, sub_topic, payload)
        writer.close()
        await writer.wait_closed()

    def build_topic_name(self, sub_topic) -> str:
        """Обратной связи нет, только включение и выключение по расписанию"""
        pass

    def receive(self, topic, payload):
        """Обратной связи нет, только включение и выключение по расписанию"""
        pass
