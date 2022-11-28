#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

import argparse
import prometheus_client
import time

import emvue_collect

class EmVueMetrics:
    def __init__(self, port=9947, interval=60):
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
            usage = emvue_collect.collect_usage()
            guages_unused = set(self.guages.keys())
            for dev_name, dev in usage.items():
                ch = dev['channels']['Main']
                power_guage_name = f"{dev_name.replace('-', '_')}_power"
                guages_unused.discard(power_guage_name)
                guage = self.get_guage(power_guage_name, "Power (W)")
                guage.set(ch['usage'])
            for name in guages_unused:
                prometheus_client.REGISTRY.unregister(self.guages[name])
                del self.guages[name]

            time.sleep(self.interval)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', '-p', type=int, default=9947)
    parser.add_argument('--interval', '-n', type=int, default=60)
    args = parser.parse_args()

    metrics = EmVueMetrics(port=args.port, interval=args.interval)
    try:
        metrics.run()
    except KeyboardInterrupt:
        pass
