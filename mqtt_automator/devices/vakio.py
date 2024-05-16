import logging

from mqtt_automator.devices.base import BaseClient

log = logging.getLogger(__name__)


class VakioClient(BaseClient):
    def receive(self, topic: str, payload: str):
        sub_topic = topic.split('/')[-1]
        value = int(payload) if payload.isdigit() else payload
        self.update_state(sub_topic, value)

    def subscriptions(self):
        for sub_topic in ('state', 'workmode', 'speed'):
            yield self.build_topic_name(sub_topic)

    def build_topic_name(self, sub_topic) -> str:
        """
        >>> cabinet = VakioClient('cabinet_mqtt', 'cabinet_pretty_name', '127.0.0.1')
        >>> cabinet.build_topic_name('speed')
        'cabinet_mqtt/speed'
        """
        return f'{self.device_id}/{sub_topic}'

    async def disable(self):
        await self.publish('state', 'off')

    async def enable(self):
        await self.publish('state', 'on')

    async def set_speed(self, speed: int):
        if speed < 1 or speed > 7:
            return
        await self.publish('speed', payload=speed)

    async def recuperate(self):
        await self.publish('workmode', 'recuperator')

    async def register_again(self):
        await self.publish('system', '0687')

    async def update(self):
        await self.publish('system', '0609')
