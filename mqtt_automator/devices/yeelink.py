import asyncio
import json
import logging

from mqtt_automator.broker import Broker
from mqtt_automator.devices.base import BaseClient, Device

log = logging.getLogger(__name__)


class YeelinkClient(BaseClient):
    port = 55443
    max_message_id = 65000

    def __init__(self, device: Device, broker: Broker = None):
        super().__init__(device, broker)
        self.message_id = 0

    def subscriptions(self):
        """Not subscribing on lamps, there is no MQTT at all, it's enough to disable it at 23:00"""
        return ()

    async def is_parent_alive(self) -> bool:
        if not self.device.parent:
            log.warning('Define parent host in device %s to use icmp value, defaulting to `on`', self.device.name)
            return True

        proc = await asyncio.create_subprocess_exec(
            'ping', '-qw1', '-c', '1', self.device.parent,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        log.debug("Parent of %s (%s) availability: %s", self.device.name, self.device.parent, not proc.returncode)
        return not proc.returncode

    async def publish(self, sub_topic: str, payload):
        if payload == 'icmp':
            payload = await self.is_parent_alive()

        if self.state.get(sub_topic) == payload:
            log.debug('Skipped because state-match %s', self.state)
            return

        self.message_id = ((self.message_id + 1) % self.max_message_id) + 1
        self.state[sub_topic] = payload
        fut = asyncio.open_connection(self.device.id, self.port)
        try:
            _, writer = await asyncio.wait_for(fut, timeout=3)
        except (OSError, asyncio.TimeoutError):
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
