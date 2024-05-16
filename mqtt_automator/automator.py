#!/usr/bin/env python3
import asyncio
import logging

from datetime import datetime

from mqtt_automator.broker import Broker
from mqtt_automator.config.parser import ConfigParser
from mqtt_automator.devices import base, vakio, lytko, yeelink

log = logging.getLogger(__name__)


class Automator:
    client_map = {
        'lytko': lytko.LytkoClient,
        'vakio': vakio.VakioClient,
        'yeelink': yeelink.YeelinkClient,
    }

    def __init__(self):
        self.config = ConfigParser()
        logging.basicConfig(
            level=logging.getLevelName(self.config.settings.get('log_level', 'INFO')),
            format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s:%(lineno)d: %(message)s'
        )
        self.broker = Broker(**self.config.broker)
        self.devices: dict[str, base.BaseClient] = {
            device_name: self.client_map[vendor](device_id, device_name, self.broker)
            for vendor, device_name, device_id
            in self.config.get_devices()
        }

    async def run(self):
        log.info('main')
        await asyncio.wait([
            asyncio.create_task(self.feedback()),
            asyncio.create_task(self.scheduler())
        ])

    async def feedback(self):
        """mqtt_client is transport to a broker, device_client is a specific for device management"""
        subscriptions = dict()
        async with self.broker.get_client() as mqtt_client:
            for device_client in self.devices.values():
                for topic in device_client.subscriptions():
                    log.info('Subscribing to %s', topic)
                    subscriptions[topic] = device_client
                    await mqtt_client.subscribe(topic=topic)  # noqa

            try:
                async for message in mqtt_client.messages:
                    device_client = subscriptions.get(message.topic.value)
                    if not device_client:
                        log.warning('Device client not found for %s', message.topic)
                        continue
                    log.debug('Received %s: %s', message.topic, message.payload)
                    device_client.receive(message.topic.value, message.payload.decode())
                    log.debug('State of %s: %s', device_client.device_id, device_client.state)

            except asyncio.CancelledError:
                log.info('Received cancel')
                for topic in subscriptions:
                    log.info('Unsubscribing from %s', topic)
                    await mqtt_client.unsubscribe(topic=topic)  # noqa
                raise

    async def scheduler(self):
        noop = dict()
        log.info('Waiting 5 seconds to init state from subscriptions')
        await asyncio.sleep(5)

        while True:
            for device, name, rule in self.config.get_active_rules():
                client: base.BaseClient = self.devices[device]
                await self.apply_actions(client, device, name, rule.get('action', noop))
                for sub_name, sub_rule in self.config.get_active_sub_rules(rule.get('sub_rules', noop)):
                    await self.apply_actions(client, device, sub_name, sub_rule['action'])

            until_start_of_next_minute = 60 - datetime.now().time().second
            await asyncio.sleep(until_start_of_next_minute)

    @staticmethod
    async def apply_actions(client, device, name, actions: dict):
        for sub_topic, payload in actions.items():
            log.debug('Applying %s %s %s %s', device, name, sub_topic, payload)
            await client.publish(sub_topic, payload)


def main_cli():
    try:
        asyncio.run(Automator().run())
    except KeyboardInterrupt:
        log.info('Finished')


if __name__ == '__main__':
    main_cli()
