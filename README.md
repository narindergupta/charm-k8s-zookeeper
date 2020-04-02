
Juju Charm for Mon on Kubernetes
==================================

Overview
---------

Zookeeper for Juju CAAS

Usage
---------

To use, first pull in dependencies via `git submodule`:

```bash
git submodule init
git submodule update
```

Then, deploy the charm with an appropriate image resource:

```bash
juju --debug deploy . --resource zookeeper_image=zookeeper:3.1
```
