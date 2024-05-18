import os
from pathlib import Path

import freezegun as freezegun
import pytest
from mqtt_automator.config.parser import ConfigParser
from mqtt_automator.devices.base import Device


@pytest.fixture(autouse=True)
def set_cwd():
    cwd = Path('.').absolute()
    if cwd.name == 'tests':
        os.chdir(cwd.parent)


@pytest.fixture
def config():
    return ConfigParser('examples/config_example.yml')


def test_config_example(config):
    assert config.broker.ip == '192.168.1.120'
    assert config.broker.protocol == 5
    assert list(config.get_devices()) == [
        Device(vendor='vakio', id='cabinet', name='cabinet'),
        Device(vendor='vakio', id='restroom', name='restroom'),
        Device(vendor='lytko', id='12345', name='floor'),
        Device(vendor='yeelink', id='192.168.1.121', name='light1'),
        Device(vendor='yeelink', id='192.168.1.122', name='light2'),
    ]


@pytest.mark.parametrize('time_to_freeze', ('2024-05-17 20:00', '2024-05-18 20:15'))
def test_get_active_rules_evening(config, time_to_freeze):
    """ Difference between workday and weekday is located at sub-rules level"""
    with freezegun.freeze_time(time_to_freeze):
        assert list(config.get_active_rules()) == [
            ('cabinet', 'day', {'workday': '18:00-22:29', 'weekend': '09:30-22:29', 'action': {'speed': 3}}),
            ('restroom', 'before_sleep', {'time': '20:00-21:59', 'action': {'state': True, 'speed': 3}}),
            ('floor', 'day', {'time': '12:00-20:29', 'action': {'mode': True, 'temperature': 18}}),
            ('light1', 'evening', {'time': '19:00-22:59', 'action': {'set_power': True}}),
            ('light2', 'evening', {'time': '19:00-22:59', 'action': {'set_power': True}})
        ]


def test_get_active_sub_rules_at_work(config):
    """ Difference between workday and weekday is located at sub-rules level"""
    with freezegun.freeze_time('2024-05-17 14:58'):
        cabinet = next(config.get_active_rules())
        assert cabinet == ('cabinet', 'at_work', {
                'workday': '09:15-18:00',
                'sub_rules': {
                    'before_meetings': {'hours': '11-15', 'minutes': '55-59', 'action': {'speed': 7}},
                    'meetings': {'hours': '12-15', 'minutes': '0-15', 'action': {'speed': 1}},
                    'fallback': {'action': {'speed': 3}}
                }
        })
        assert list(config.get_active_sub_rules(cabinet[2]['sub_rules'])) == [
            ('before_meetings', {'hours': '11-15', 'minutes': '55-59', 'action': {'speed': 7}})
        ]
