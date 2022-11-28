# SPDX-License-Identifier: BSD-3-Clause
import datetime
import json
import pyemvue
import sys
import time

from pyemvue.enums import Scale, Unit

try:
    with open('.user.json') as f:
        user_auth = json.load(f)
except FileNotFoundError:
    sys.exit('Expected .user.json file with {"user": "...", "password": "..."}')

vue = pyemvue.PyEmVue()
vue.login(username=user_auth['user'], password=user_auth['password'],
          token_storage_file='.keys.json')

def sumarize_multi_dev(data):
    for name in list(data.keys()):
        if name.split('-')[-1].isnumeric():
            sumary_name = '-'.join(name.split('-')[:-1])
            if sumary_name not in data:
                data[sumary_name] = {
                    'name': sumary_name,
                    'devs': [],
                    'channels': {},
                }
            data[sumary_name]['devs'].append(name)
            for ch_name in data[name]['channels']:
                ch = data[name]['channels'][ch_name]
                if ch_name not in data[sumary_name]['channels']:
                    data[sumary_name]['channels'][ch_name] = {
                        'name': ch_name,
                        'usage': ch['usage'],
                    }
                else:
                    data[sumary_name]['channels'][ch_name]['usage'] += ch['usage']

def collect_usage(retrys=3):
    while True:
        try:
            usage_data = {}

            devices = vue.get_devices()
            device_gids = set(d.device_gid for d in devices)

            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-7)))
            usageDict = vue.get_device_list_usage(list(device_gids), now, Scale.MINUTE.value, Unit.KWH.value)

            for gid, dev in usageDict.items():
                props = vue.populate_device_properties(dev)
                channel_data = {}
                for num, ch in dev.channels.items():
                    scaled_usage = 0
                    if ch.usage:
                        scaled_usage = ch.usage * 1000 * 3600 / 60
                    channel_data[ch.name] = {
                        'name': ch.name,
                        'usage': scaled_usage
                    }
                usage_data[props.device_name] = {
                    'name': props.device_name,
                    'location': (props.latitude, props.longitude),
                    'channels': channel_data,
                }

            sumarize_multi_dev(usage_data)

            return usage_data
        except TypeError:
            retrys -= 1
            if retrys == 0:
                raise
            time.sleep(1)
