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
Then run the following command:
```
./emvue-exporter.py
```
If you point a browser at ```localhost:9947``` you should see the
metrics for the Emporia devices linked to your account. For more usage
options:
```
./emvue-exporter.py -h
```

[ref-prom]: https://prometheus.io/
[ref-emporia]: https://web.emporiaenergy.com/
[ref-prom-port]:https://github.com/prometheus/prometheus/wiki/Default-port-allocations
