# emvue-exporter

A [Prometheus][ref-prom] exporter for [Emporia Energy][ref-emporia]
smart devices.

## Overview

This repo contains a Python-based Prometheus metric exporter for
Emporia smart devices. This can then be combined with Grafana for
dashboard viewing. Note that the default port used (9947) has been
reserved on the [Prometheus Wiki][ref-prom-port].

## Usage

Place a file called ```.user.json``` in the base directory of this
repo. It should contain the following:
```
{
    "username": "<Emporia Username>"
    "password": "<Emporia Password>"
}
```
See the pypi entry for the [PyEmVue module][ref-pyemvue] for more
information. Then run the following command:
```
./emvue-exporter.py
```
If you point a browser at ```localhost:9947``` you should see the
metrics for the Emporia devices linked to your account. For more usage
options:
```
./emvue-exporter.py -h
```

## Metrics

Every plug on the account is reported through the same two metric
families, one series per plug:

```
# HELP emvue_plug_power_watts Mean power drawn by the plug over the last minute (Watts).
# TYPE emvue_plug_power_watts gauge
emvue_plug_power_watts{plug="snoc-pinewood-plug-a",name="Outside lights"} 75.4
# HELP emvue_plug_on Outlet state: 1 when on, 0 when off.
# TYPE emvue_plug_on gauge
emvue_plug_on{plug="snoc-pinewood-plug-a",name="Outside lights"} 1.0
```

The ```plug``` label is the Emporia device name. Because these are
families rather than one metric name per plug, a dashboard needs only
a single query, ```emvue_plug_power_watts``` with a legend format of
```{{name}}```, and picks up new plugs on its own.

## Plug labels

Further Prometheus labels per plug are defined in a JSON file passed
with ```--labels_file```. Keys must match the Emporia device name,
either as-is or with hyphens replaced by underscores (for example
```snoc_pinewood_plug_a```). Each plug maps to an object of label
name/value pairs:

```
{
    "snoc_pinewood_plug_a": {
        "name": "Utility room",
        "room": "basement"
    },
    "snoc_pinewood_plug_b": {
        "name": "Garage freezer"
    }
}
```

Use ```name``` for the human-readable plug name; it is the label
Grafana legends are expected to key on. A bare string per plug is
still accepted as shorthand for a single ```location``` label. Label
names must be valid Prometheus label names (letters, digits,
underscore).

A metric family carries one fixed label set, so the exporter takes the
union of the label names across every plug and gives a plug that omits
one an empty value for it. Prometheus drops empty labels on ingest, so
a plug listed with no labels at all is served as
```emvue_plug_power_watts{plug="..."}``` and nothing more. The
```--labels_file``` argument itself is optional.

Example:

```
./emvue-exporter.py --labels_file labels.json
```

## Systemd Service Install

You can install this as a systemd service on your using via the
following steps (tested on Ubuntu 24.04):

1. ```sudo python3 -m venv /usr/local/venvs/emvue-exporter```.
1. ```sudo /usr/local/venvs/emvue-exporter/bin/pip install -r requirements.txt```.
1. ```sudo cp emvue-exporter.py /usr/local/bin```.
1. ```sudo cp emvue-exporter.service /etc/systemd/system/```.
1. ```sudo mkdir -p /usr/local/share/emvue-exporter```.
1. ```sudo cp .user.json /usr/local/share/emvue-exporter/.user.json```.
1. ```sudo touch /usr/local/share/emvue-exporter/.keys.json```.
1. ```sudo cp labels.json /usr/local/share/emvue-exporter/labels.json```
   -- ```labels.json``` here is an example; substitute your own, which
   is site configuration and belongs in whatever repo holds the rest
   of it rather than in this one.
1. ```sudo systemctl daemon-reload```
1. ```sudo systemctl enable emvue-exporter.service```
1. ```sudo systemctl start emvue-exporter.service```

[ref-prom]: https://prometheus.io/
[ref-emporia]: https://web.emporiaenergy.com/
[ref-prom-port]:https://github.com/prometheus/prometheus/wiki/Default-port-allocations
[ref-pyemvue]: https://pypi.org/project/pyemvue/
