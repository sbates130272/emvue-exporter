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
        self.power_guages = {}
        self.on_enums = {}

    def init_power_guage(self, name, desc):
        self.power_guages[name] = pc.Gauge(name,
                                           desc,
                                           registry=pc.REGISTRY)
    def init_on_enum(self, name, desc):
        self.on_enums[name] = pc.Enum(name,
                                      desc,
                                      states=['on', 'off'],
                                      registry=pc.REGISTRY)

    def run(self):
        pc.start_http_server(port=self.port)
        while True:
            outlets = vue.get_outlets()
            usage = emvue_collect_usage()
            print("emvue-exporter: updating exporter page.")
            for gid, dev in usage.items():
                dev = vue.populate_device_properties(dev)
                ch = dev.channels[list(dev.channels.keys())[0]]
                gname = f"{dev.device_name.replace('-', '_')}_power"
                if not ch.usage:
                    ch.usage = 0
                else:
                    ch.usage *= 1000*60
                if gname not in self.power_guages:
                    self.init_power_guage(gname,
                                          "Energy measurement (Joules).")
                self.power_guages[gname].set(ch.usage)
                outlet = None
                for o in outlets:
                    if o.device_gid == dev.device_gid:
                        outlet = o
                if outlet:
                    ename = f"{dev.device_name.replace('-', '_')}_on"
                    if ename not in self.on_enums:
                        self.init_on_enum(ename,
                                          "Outlet state (on or off).")
                    if outlet.outlet_on:
                        self.on_enums[ename].state("on")
                    else:
                        self.on_enums[ename].state("off")

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

    vue = pyemvue.PyEmVue()
    try:
        with open(args.token_file) as f:
            data = json.load(f)

        vue.login(id_token=data['id_token'],
                  access_token=data['access_token'],
                  refresh_token=data['refresh_token'],
                  token_storage_file=args.token_file)
    except:
        with open(args.auth_file) as f:
            data = json.load(f)
        vue.login(username=data['username'],
                  password=data['password'],
                  token_storage_file=args.token_file)

    print("emvue-exporter: connected to Emporia web-server.")
    exporter = emVueMetricsExporter(port=args.port,
                                    interval=args.interval)
    try:
        exporter.run()
    except KeyboardInterrupt:
        pass
