#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

import argparse
import json
import time

import prometheus_client as pc
import pyemvue
from pyemvue.enums import Scale, Unit


def normalize_plug_labels(value):
    """Return non-empty string labels for one plug (Prometheus label values)."""
    if isinstance(value, str):
        if not value.strip():
            return {}
        return {"location": value.strip()}
    if isinstance(value, dict):
        return {
            str(k): str(v).strip()
            for k, v in value.items()
            if v is not None and str(v).strip()
        }
    return {}


def load_plug_labels(labels_file):
    """
    Load per-plug Prometheus labels from JSON.

    Each plug ID maps to an object of label name/value pairs, e.g.:
      "snoc_pinewood_plug_a": {"location": "Utility", "room": "basement"}

    A bare string per plug is accepted as shorthand for
    {"location": "<string>"}. A top-level "labels" object is also accepted.
    """
    with open(labels_file, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{labels_file}: root must be a JSON object")
    if isinstance(data.get("labels"), dict):
        raw = data["labels"]
    else:
        raw = data
    return {
        str(plug_id): normalize_plug_labels(label_value)
        for plug_id, label_value in raw.items()
    }


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

    def __init__(self, port, interval, labels_file):
        self.port = port
        self.interval = interval
        self.plug_labels = load_plug_labels(labels_file) if labels_file else {}
        self.power_gauges = {}
        self.on_enums = {}

    def plug_id_from_device(self, device_name):
        return device_name.replace("-", "_")

    def get_plug_labels(self, plug_id):
        return self.plug_labels.get(plug_id, {})

    def init_power_gauge(self, name, desc, labelnames):
        if name not in self.power_gauges:
            names = sorted(labelnames) if labelnames else ()
            if names:
                self.power_gauges[name] = pc.Gauge(
                    name,
                    desc,
                    labelnames=names,
                    registry=pc.REGISTRY,
                )
            else:
                self.power_gauges[name] = pc.Gauge(
                    name,
                    desc,
                    registry=pc.REGISTRY,
                )
        return self.power_gauges[name]

    def init_on_enum(self, name, desc, labelnames):
        if name not in self.on_enums:
            names = sorted(labelnames) if labelnames else ()
            if names:
                self.on_enums[name] = pc.Enum(
                    name,
                    desc,
                    states=["on", "off"],
                    labelnames=names,
                    registry=pc.REGISTRY,
                )
            else:
                self.on_enums[name] = pc.Enum(
                    name,
                    desc,
                    states=["on", "off"],
                    registry=pc.REGISTRY,
                )
        return self.on_enums[name]

    def set_power(self, name, desc, plug_labels, value):
        gauge = self.init_power_gauge(name, desc, plug_labels.keys())
        if plug_labels:
            gauge.labels(**plug_labels).set(value)
        else:
            gauge.set(value)

    def set_on_state(self, name, desc, plug_labels, outlet_on):
        enum = self.init_on_enum(name, desc, plug_labels.keys())
        state = "on" if outlet_on else "off"
        if plug_labels:
            enum.labels(**plug_labels).state(state)
        else:
            enum.state(state)

    def run(self):
        pc.start_http_server(port=self.port)
        while True:
            outlets = vue.get_outlets()
            usage = emvue_collect_usage()
            print("emvue-exporter: updating exporter page.")
            for gid, dev in usage.items():
                dev = vue.populate_device_properties(dev)
                ch = dev.channels[list(dev.channels.keys())[0]]
                plug_id = self.plug_id_from_device(dev.device_name)
                plug_labels = self.get_plug_labels(plug_id)
                gname = f"{plug_id}_power"
                if not ch.usage:
                    ch.usage = 0
                else:
                    ch.usage *= 1000 * 60
                self.set_power(
                    gname,
                    "Energy measurement (Joules).",
                    plug_labels,
                    ch.usage,
                )
                outlet = None
                for o in outlets:
                    if o.device_gid == dev.device_gid:
                        outlet = o
                if outlet:
                    ename = f"{plug_id}_on"
                    self.set_on_state(
                        ename,
                        "Outlet state (on or off).",
                        plug_labels,
                        outlet.outlet_on,
                    )

            time.sleep(self.interval)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="A metrics exporter for Emporia Vue smart devices.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--port",
        "-p",
        metavar="PORT",
        type=int,
        default=9947,
        help="The TCP/IP port to put metrics on.",
    )
    parser.add_argument(
        "--interval",
        "-n",
        metavar="SCRAPE_INTERVAL",
        type=int,
        default=120,
        help="The interval at which to update metrics.",
    )
    parser.add_argument(
        "--auth_file",
        metavar="AUTH_FILE",
        default=".user.json",
        help="The authorization file for the Emporia web-site.",
    )
    parser.add_argument(
        "--token_file",
        metavar="AUTH_FILE",
        default=".keys.json",
        help="The token file for the Emporia web-site.",
    )
    parser.add_argument(
        "--labels_file",
        metavar="LABELS_FILE",
        default=None,
        help=(
            "JSON file mapping each plug ID to Prometheus label key/value "
            "pairs (objects), or a location string shorthand"
        ),
    )
    args = parser.parse_args()

    vue = pyemvue.PyEmVue()
    try:
        with open(args.token_file, encoding="utf-8") as f:
            data = json.load(f)

        vue.login(
            id_token=data["id_token"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_storage_file=args.token_file,
        )
    except Exception:
        with open(args.auth_file, encoding="utf-8") as f:
            data = json.load(f)
        vue.login(
            username=data["username"],
            password=data["password"],
            token_storage_file=args.token_file,
        )

    print("emvue-exporter: connected to Emporia web-server.")
    exporter = emVueMetricsExporter(
        port=args.port,
        interval=args.interval,
        labels_file=args.labels_file,
    )
    try:
        exporter.run()
    except KeyboardInterrupt:
        pass
