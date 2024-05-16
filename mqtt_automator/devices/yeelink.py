import asyncio
import json
import logging

from mqtt_automator.broker import Broker
from mqtt_automator.devices.base import BaseClient

log = logging.getLogger(__name__)


class YeelinkClient(BaseClient):
    port = 55443
    max_message_id = 65000

    def __init__(self, device_id: str, device_name: str, broker: Broker = None):
        super().__init__(device_id, device_name, broker)
        self.message_id = 0

    def subscriptions(self):
        """Not subscribing on lamps, there is no MQTT at all, it's enough to disable it at 23:00"""
        return ()

    async def publish(self, sub_topic: str, payload):
        if self.state.get(sub_topic) == payload:
            log.debug('Skipped because state-match %s', self.state)
            return

        self.message_id = ((self.message_id + 1) % self.max_message_id) + 1
        self.state[sub_topic] = payload
        try:
            _, writer = await asyncio.open_connection(self.device_id, self.port)
        except OSError:
            # If device is switched off, no problem, keep _desired_ state and skip further requests
            log.warning("Can't connect to %s", self)
            return
        writer.write(
            (
                    json.dumps({
                        'id': self.message_id,
                        'method': sub_topic,
                        'params': ['on', 'smooth', 500] if payload else ['off']
                    })
                    + '\r\n'
            ).encode()
        )
        await writer.drain()
        log.info('Published %s %s %s', self, sub_topic, payload)
        writer.close()
        await writer.wait_closed()

    def build_topic_name(self, sub_topic) -> str:
        """No feedback is required, just turn on and turn off by schedule"""
        raise NotImplementedError

    def receive(self, topic, payload):
        """No feedback is required, just turn on and turn off by schedule"""
        raise NotImplementedError
