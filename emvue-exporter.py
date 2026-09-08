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


def plug_key(name):
    "Normalize a plug ID or Emporia device name to a lookup key."
    return str(name).replace("-", "_")


def load_plug_labels(labels_file):
    """
    Load per-plug Prometheus labels from JSON.

    Each plug ID maps to an object of label name/value pairs, e.g.:
      "snoc_pinewood_plug_a": {"name": "Utility", "room": "basement"}

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
        plug_key(plug_id): normalize_plug_labels(label_value)
        for plug_id, label_value in raw.items()
    }


def label_schema(plug_labels):
    """
    Return the label names every plug series must carry.

    A Prometheus metric family has one fixed label set, but each plug
    configures whatever labels it likes, so the family takes the union
    of them all and plugs that omit one get an empty value for it.
    """
    names = set()
    for labels in plug_labels.values():
        names.update(labels)
    return ("plug",) + tuple(sorted(names))


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
        self.labelnames = label_schema(self.plug_labels)
        self.power = pc.Gauge(
            "emvue_plug_power_watts",
            "Mean power drawn by the plug over the last minute (Watts).",
            labelnames=self.labelnames,
            registry=pc.REGISTRY,
        )
        self.on = pc.Gauge(
            "emvue_plug_on",
            "Outlet state: 1 when on, 0 when off.",
            labelnames=self.labelnames,
            registry=pc.REGISTRY,
        )

    def get_plug_labels(self, device_name):
        "Return the full label set for one plug, empties included."
        configured = self.plug_labels.get(plug_key(device_name), {})
        labels = {"plug": device_name}
        for name in self.labelnames[1:]:
            labels[name] = configured.get(name, "")
        return labels

    def run(self):
        pc.start_http_server(port=self.port)
        while True:
            outlets = vue.get_outlets()
            usage = emvue_collect_usage()
            print("emvue-exporter: updating exporter page.")
            # A plug taken off the account otherwise keeps serving its
            # last reading for ever: the series never goes stale, it
            # just stops moving.
            self.power.clear()
            self.on.clear()
            for gid, dev in usage.items():
                dev = vue.populate_device_properties(dev)
                ch = dev.channels[list(dev.channels.keys())[0]]
                plug_labels = self.get_plug_labels(dev.device_name)
                # The API reports kWh accumulated over the last minute.
                # Scaling to Wh and then to an hourly rate gives the
                # mean power over that minute.
                watts = (ch.usage or 0) * 1000 * 60
                self.power.labels(**plug_labels).set(watts)
                outlet = None
                for o in outlets:
                    if o.device_gid == dev.device_gid:
                        outlet = o
                if outlet:
                    self.on.labels(**plug_labels).set(
                        1 if outlet.outlet_on else 0
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
            "pairs (objects), or a location string shorthand. Use a 'name' "
            "label for the human-readable plug name"
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
