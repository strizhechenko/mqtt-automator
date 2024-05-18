import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Self

from pydantic import BaseModel, Field, model_validator, ValidationError
import yaml

from mqtt_automator.config.time_parser import match_time_range, match_range
from mqtt_automator.broker import Broker
from mqtt_automator.devices.base import Device

log = logging.getLogger(__name__)


class Settings(BaseModel):
    log_level: str = Field(default='INFO')


class Rule(BaseModel):
    """
    Rules are dictionaries with following members:
    - workday - time range when rule will be active from monday to friday
    - weekend - time range when rule will be active from saturday/sunday (there will be custom holidays later)
    - time - time range when rule will be active independently of the day of the week
    - action - dictionary of topic=payload that will be passed to the device when rule is active (optional)
    - sub_rules - alternative to action if device should repeatedly change workmode.
    """
    workday: Optional[str] = Field(pattern=r'\d{2}:\d{2}-\d{2}:\d{2}', default=None)
    weekend: Optional[str] = Field(pattern=r'\d{2}:\d{2}-\d{2}:\d{2}', default=None)
    time: Optional[str] = Field(pattern=r'\d{2}:\d{2}-\d{2}:\d{2}', default=None)
    action: Optional[dict] = Field(default=None)
    sub_rules: Optional[dict] = Field(default=None)

    @model_validator(mode='after')
    def at_least_one_time_defined(self) -> Self:
        if self.time:
            if not self.weekend and not self.workday:
                return self
        elif self.weekend or self.workday:
            return self
        raise ValueError('Schedule is not defined or too defined')

    @model_validator(mode='after')
    def full_or_split(self) -> Self:
        if self.action and self.sub_rules:
            raise ValueError('Do not combine action and sub_rules in a single rule')
        if not self.action and not self.sub_rules:
            raise ValueError('action or sub_rules required')
        return self


class SubRule(BaseModel):
    """
    Sub-rules are dictionaries with following members:
    - action - same as action in rules, but it's required now.
    - hours: range when sub-rule is active. Example: 11-15. Parent rule must be active too.
    - minutes: same as hours but for minutes. Example: 15-59.

    Special sub-rules:
    - fallback: if no sub-rule is active this sub-rule will be applied. Doesn't contain hours/minutes.
    """
    hours: Optional[str] = Field(pattern=r'\d{1,2}-\d{1,2}', default=None)
    minutes: Optional[str] = Field(pattern=r'\d{1,2}-\d{1,2}', default=None)
    action: dict


class ConfigParser:
    system_keys = {'app', 'broker'}

    def __init__(self, file_name: str = 'config.yml'):
        """
        config.yml should have a root-members:
        broker:
            ip: IPv4 of MQTT-broker
            protocol: version of MQTT proto used by broker (default 5)
        app:
            log_level: DEBUG (default INFO)
        """
        self.config = yaml.load(Path(file_name).read_text('utf-8'), yaml.SafeLoader)
        self.broker = Broker(**self.config['broker'])
        self.settings = Settings(**(self.config.get('app') or {}))

    def get_devices(self):
        """
        Generator that yields: tuple(vendor: str, device_name: str, device_id: str)

        vendors are living in the root of config to prevent highly nested structure

        - vendor - vendor name to match with client class
        - device_name - human-oriented identifier given in config.yml
        - device_id - identifier used to build read and write topics names in MQTT brokers, sometimes can't be changed.
            if not specified, device_name is used as device_id

        config.yml structure is:

        vendor_name_1:
            device_name_1:
                device: device_id_1
                $rules$
            device_name_2:
                device: device_id_2
        """
        for vendor, devices in self.config.items():
            if vendor in self.system_keys:
                continue
            for device_name, device in devices.items():
                if device_name == 'common':
                    continue
                yield Device(vendor=vendor, name=device_name, id=device.get('device', device_name))

    def get_active_rules(self):
        """For rule structure see class Rule"""
        now = datetime.now()
        is_workday, now_time = now.isoweekday() <= 5, now.time()
        for vendor, devices in self.config.items():
            if vendor in self.system_keys:
                continue

            common = devices['common'] if 'common' in devices else dict()

            for device, rules in devices.items():
                if device == 'common':
                    continue

                log.debug('Looking for device %s', device)
                for name, rule_ in (rules | common).items():
                    if name == 'device':
                        continue
                    rule = Rule(**rule_)
                    schedule = (rule.workday if is_workday else rule.weekend) or rule.time
                    log.debug('Checking rule %s schedule %s', name, schedule)
                    if schedule and match_time_range(schedule, now_time):
                        log.debug('rule %s schedule %s matched! yielding %s', name, schedule, rule)
                        yield device, name, rule.model_dump(exclude_unset=True)

    @staticmethod
    def get_active_sub_rules(sub_rules: dict):
        """For sub-rule structure see class SubRule"""
        found, has_fallback = False, False
        now = datetime.now().time()

        for name, rule_ in sub_rules.items():
            try:
                rule = SubRule(**rule_)
            except ValidationError:
                log.info("Bad rule %s", rule_, exc_info=True)
                continue

            if name == 'fallback':
                has_fallback = True
            elif rule.hours and not match_range(rule.hours, now.hour):
                pass
            elif rule.minutes and not match_range(rule.minutes, now.minute):
                pass
            else:
                found = True
                yield name, rule.model_dump(exclude_unset=True)

        if not found and has_fallback:
            yield 'fallback', sub_rules['fallback']
