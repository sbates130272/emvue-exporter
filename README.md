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
1. ```sudo systemctl daemon-reload```
1. ```sudo systemctl enable emvue-exporter.service```
1. ```sudo systemctl start emvue-exporter.service```

[ref-prom]: https://prometheus.io/
[ref-emporia]: https://web.emporiaenergy.com/
[ref-prom-port]:https://github.com/prometheus/prometheus/wiki/Default-port-allocations
[ref-pyemvue]: https://pypi.org/project/pyemvue/
