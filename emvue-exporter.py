#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

import datetime
import prometheus_client as pc
import pyemvue
from pyemvue.enums import Scale, Unit
import time

def emvue_collect_usage():
    "A function that contacts the Emproia cloud server and gathers \
    usage stats on the devices associated with the provided \
    account. We do this for the last 60 seconds as a KWH measurement."

    devices = vue.get_devices()
    gids = []
    for device in devices:
        gids.append(device.device_gid)
    usage = vue.get_device_list_usage(
        gids,
        None,
        Scale.MINUTE.value,
        Unit.KWH.value)

    return usage

class emVueMetricsExporter:

    def __init__(self, port, interval):
        self.port = port
        self.interval = interval
        self.guages = {}

    def init_guage(self, name, desc):
        self.guages[name] = pc.Gauge(name,
                                     desc,
                                     registry=pc.REGISTRY)

    def run(self):
        pc.start_http_server(port=self.port)
        while True:
            usage = emvue_collect_usage()
            for gid, dev in usage.items():
                dev = vue.populate_device_properties(dev)
                ch = dev.channels[list(dev.channels.keys())[0]]
                name = f"{dev.device_name.replace('-', '_')}"
                if not ch.usage:
                    ch.usage = 0
                else:
                    ch.usage *= 1000*60
                if name not in self.guages:
                    self.init_guage(name,
                                    "Energy measurement (Joules).")
                self.guages[name].set(ch.usage)

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
                        type=int, default=120,
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
    exporter = emVueMetricsExporter(port=args.port,
                                    interval=args.interval)
    try:
        exporter.run()
    except KeyboardInterrupt:
        pass
