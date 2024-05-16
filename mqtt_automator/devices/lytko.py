import logging
import json

from mqtt_automator.devices.base import BaseClient

log = logging.getLogger(__name__)


class LytkoClient(BaseClient):
    def receive(self, topic: str, payload: str):
        payload = json.loads(payload)
        state = {
            'mode': 'off' if payload['heating'] == 'off' else 'on',
            'temperature': int(float(payload['target_temp']))
        }
        for sub_topic, value in state.items():
            self.update_state(sub_topic, value)

    def subscriptions(self):
        """
        >>> floor = LytkoClient('12345', 'floor_pretty_name', '127.0.0.1')
        >>> list(floor.subscriptions())
        ['climate/lytko/12345/state']
        """
        yield f'climate/lytko/{self.device_id}/state'

    def build_topic_name(self, sub_topic) -> str:
        """
        >>> floor = LytkoClient('12345', 'floor_pretty_name', '127.0.0.1')
        >>> floor.build_topic_name('temperature')
        'climate/lytko/12345/temperature/set'
        """
        return f'climate/lytko/{self.device_id}/{sub_topic}/set'

    async def enable(self):
        await self.publish('mode', 'heat')

    async def disable(self):
        await self.publish('mode', 'off')

    async def set_temperature(self, temperature):
        await self.publish('temperature', temperature)
