import logging
from datetime import datetime
from pathlib import Path

import yaml

from mqtt_automator.config.time_parser import match_time_range, match_range

log = logging.getLogger(__name__)


class ConfigParser:
    system_keys = {'app', 'broker'}

    def __init__(self):
        """
        config.yml should have a root-members:
        broker:
            ip: IPv4 of MQTT-broker
            protocol: version of MQTT proto used by broker (default 5)
        app:
            log_level: DEBUG (default INFO)
        """
        self.config = yaml.load(Path('config.yml').read_text('utf-8'), yaml.SafeLoader)
        self.broker: dict = self.config['broker']
        self.settings: dict = self.config['app']

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
                yield vendor, device_name, device.get('device', device_name)

    def get_active_rules(self):
        """
        Rules are dictionaries with following members:
        - workday - time range when rule will be active from monday to friday
        - weekend - time range when rule will be active from saturday/sunday (there will be custom holidays later)
        - time - time range when rule will be active independently of the day of the week
        - action - dictionary of topic=payload that will be passed to the device when rule is active (optional)
        - sub_rules - alternative to action if device should repeatedly change workmode.
        """
        now = datetime.now()
        is_workday, now_time = now.isoweekday() > 5, now.time()
        for vendor, devices in self.config.items():
            if vendor in self.system_keys:
                continue

            common = devices['common'] if 'common' in devices else dict()

            for device, rules in devices.items():
                if device == 'common':
                    continue

                log.debug('Looking for device %s', device)
                for name, rule in (rules | common).items():
                    if name == 'device':
                        continue
                    schedule = rule.get('workday' if is_workday else 'weekend') or rule.get('time')
                    log.debug('Checking rule %s schedule %s', name, schedule)
                    if schedule and match_time_range(schedule, now_time):
                        log.debug('rule %s schedule %s matched! yielding %s', name, schedule, rule)
                        yield device, name, rule

    @staticmethod
    def get_active_sub_rules(sub_rules: dict):
        """
        Sub-rules are dictionaries with following members:
        - action - same as action in rules, but it's required now.
        - hours: range when sub-rule is active. Example: 11-15. Parent rule must be active too.
        - minutes: same as hours but for minutes. Example: 15-59.
        - fallback: if no sub-rule is active this sub-rule will be applied.
        """
        found, has_fallback = False, False
        now = datetime.now().time()

        for name, rule in sub_rules.items():
            if 'action' not in rule:
                log.warning('%s has no action key', rule)
            elif name == 'fallback':
                has_fallback = True
            elif 'hours' in rule and not match_range(rule['hours'], now.hour):
                pass
            elif 'minutes' in rule and not match_range(rule['minutes'], now.minute):
                pass
            else:
                found = True
                yield name, rule

        if not found and has_fallback:
            yield 'fallback', sub_rules['fallback']
