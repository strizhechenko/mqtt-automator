import abc
import logging
from datetime import datetime, timedelta
from typing import Generator

from mqtt_automator.broker import Broker

CLIENT_BLOCK_SECONDS = timedelta(hours=4).seconds

log = logging.getLogger(__name__)


class BaseClient(abc.ABC):
    topic_template: str

    def __init__(self, device_id: str, device_name: str, broker: Broker = None):
        self.broker = broker
        self.device_id = device_id
        self.device_name = device_name
        self.state = dict()
        self.started_at = datetime.now()
        self.block = dict()

    def __str__(self):
        return f'{type(self).__name__.replace("Client", "")} {self.device_name} ({self.device_id})'

    async def publish(self, sub_topic: str, payload):
        if isinstance(payload, bool):
            payload = 'on' if payload else 'off'

        if self.state.get(sub_topic) == payload:
            log.debug('Skipped %s %s because state-match %s', self, sub_topic, self.state)
            return

        if sub_topic in self.block:
            if (datetime.now() - self.block[sub_topic]).seconds < CLIENT_BLOCK_SECONDS:
                log.info('Skipped %s %s update, it was blocked at %s', self, sub_topic, self.block[sub_topic])
                return
            self.block.pop(sub_topic)

        async with self.broker.get_client() as client:
            await client.publish(topic=self.build_topic_name(sub_topic), payload=payload)  # noqa
            self.state[sub_topic] = payload
            log.info('Published %s %s %s', self, sub_topic, payload)

    def update_state(self, sub_topic: str, value):
        """_Required_ to use inside subclass.receive()"""
        if self.state.get(sub_topic) == value:
            log.debug('Skipped %s %s because state-match %s', self, sub_topic, self.state)
            return

        if sub_topic in self.state:
            self.block[sub_topic] = datetime.now()
            log.info('%s blocked %s because of update', self, sub_topic)

        log.info('Updating %s state: %s %s -> %s', self, sub_topic, self.state.get(sub_topic), value)
        self.state[sub_topic] = value

    @abc.abstractmethod
    def receive(self, topic, payload):
        """
        `topic` - is full topic name, given it subclasses should parse `payload` and save it to self.state.
        Different devices have different topics and payload structure, so there is no common logic.
        """

    @abc.abstractmethod
    def subscriptions(self) -> Generator:
        """Method should return list of read-topics of device to subscribe."""

    @abc.abstractmethod
    def build_topic_name(self, sub_topic) -> str:
        """
        Method should build full write-topic name based on self.device_id.
        Different devices have different topics structure, so there is no common logic.
        """
