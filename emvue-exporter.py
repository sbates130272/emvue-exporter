#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

import datetime
import prometheus_client
import pyemvue
import time

from pyemvue.enums import Scale, Unit

def sumarize_multi_dev(data):
    for name in list(data.keys()):
        if name.split('-')[-1].isnumeric():
            sumary_name = '-'.join(name.split('-')[:-1])
            if sumary_name not in data:
                data[sumary_name] = {
                    'name': sumary_name,
                    'devs': [],
                    'channels': {},
                    'outlet': 0,
                }
            data[sumary_name]['devs'].append(name)
            data[sumary_name]['outlet'] += data[name]['outlet']
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
            dev_from_gid = {d.device_gid: d for d in devices}

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
                    'outlet': 1 if dev_from_gid[gid].outlet.outlet_on else 0,
                }

            sumarize_multi_dev(usage_data)

            return usage_data
        except TypeError:
            retrys -= 1
            if retrys == 0:
                raise
            time.sleep(1)


class EmVueMetrics:

    def __init__(self, port, interval):
        self.port = port
        self.interval = interval
        self.guages = {}

    def get_guage(self, name, desc):
        if name not in self.guages:
            self.guages[name] = prometheus_client.Gauge(name, desc,
                                    registry=prometheus_client.REGISTRY)
        return self.guages[name]

    def run(self):
        prometheus_client.start_http_server(port=self.port)

        while True:
            usage = collect_usage()
            guages_unused = set(self.guages.keys())
            for dev_name, dev in usage.items():
                ch = dev['channels']['Main']

                power_guage_name = f"{dev_name.replace('-', '_')}_power"
                guages_unused.discard(power_guage_name)
                guage = self.get_guage(power_guage_name, "Power (W)")
                guage.set(ch['usage'])

                outlet_state_name = f"{dev_name.replace('-', '_')}_outlet"
                guages_unused.discard(outlet_state_name)
                guage = self.get_guage(outlet_state_name, "Number of outlets turned on")
                guage.set(dev['outlet'])

            for name in guages_unused:
                prometheus_client.REGISTRY.unregister(self.guages[name])
                del self.guages[name]

            time.sleep(self.interval)

if __name__ == '__main__':

    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description='A metrics exporter for Emporia Vue smart devices.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--port', '-p', metavar='PORT',
                        type=int, default=9947,
                        help='The TCP/IP port to put metrics on.')
    parser.add_argument('--interval', '-n', metavar='SCRAPE_INTERVAL',
                        type=int, default=60,
                        help='The interval at which to update metrics.')
    parser.add_argument('--auth_file', metavar='AUTH_FILE', default='.user.json',
                        help='The authorization file for the Emporia web-site.')
    parser.add_argument('--token_file', metavar='AUTH_FILE', default='.keys.json',
                        help='The token file for the Emporia web-site.')
    args = parser.parse_args()

    with open(args.auth_file) as f:
        user_auth = json.load(f)

    vue = pyemvue.PyEmVue()
    vue.login(username=user_auth['username'], password=user_auth['password'],
              token_storage_file=args.token_file)
    metrics = EmVueMetrics(port=args.port, interval=args.interval)

    try:
        metrics.run()
    except KeyboardInterrupt:
        pass
