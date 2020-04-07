#!/usr/bin/env python3

import os
import subprocess
import socket
import re
import pwd
import sys
import json
import logging
import yaml

sys.path.append('lib')

from ops.charm import EventSource, EventBase, CharmBase, CharmEvents
from ops.main import main
from ops.framework import StoredState, Object
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    UnknownStatus,
    WaitingStatus,
    ModelError,
)

from interface import ZookeeperCluster
from interface import ZookeeperClient
from k8s import K8sPod

logging.basicConfig(level=logging.DEBUG)


class ZookeeperStartedEvent(EventBase):
     pass


class ZookeeperCharmEvents(CharmEvents):
     zookeeper_started = EventSource(ZookeeperStartedEvent)


class ZookeeperCharm(CharmBase):
    on = ZookeeperCharmEvents()
    state = StoredState()

    def __init__(self, framework, key):
        super().__init__(framework, key)

        self.framework.observe(self.on.start, self)
#        self.framework.observe(self.on.stop, self)
        self.framework.observe(self.on.update_status, self)
        self.framework.observe(self.on.upgrade_charm, self)
        self.framework.observe(self.on.config_changed, self)
        self.framework.observe(self.on.cluster_relation_changed, self.on_cluster_modified)
        self.framework.observe(self.on.zookeeper_relation_joined, self.expose_relation_data)

        self._unit = 1
        self._zookeeperuri = ""
        self._pod = K8sPod(self.framework.model.app.name)

        self.cluster = ZookeeperCluster(self, 'cluster')
        self.client = ZookeeperClient(self, 'zookeeper', self.model.config['client-port'])

        self.state.set_default(isStarted=False)

        self.framework.observe(self.on.leader_elected, self)

    def on_start(self, event):
        logging.info('START')
        if (self.model.pod._backend.is_leader()):
#        if not self.model.config['ha-mode']:
            #self.model.unit.status = MaintenanceStatus('Starting pod')
            podSpec = self.makePodSpec()
            self.model.pod.set_spec(podSpec)
            self.state.podSpec = podSpec
        self.on.config_changed.emit()

    def expose_relation_data(self, event):
        logging.info('Data Exposed')
        fqdn = socket.getnameinfo((str(self.cluster.ingress_address), 0), socket.NI_NAMEREQD)[0]
        logging.info(fqdn)
        self.client.set_host(fqdn)
        self.client.set_port(self.model.config['client-port'])
        self.client.set_rest_port(self.model.config['client-port'])
        self.client.expose_zookeeper()
        self.on.config_changed.emit()

    def on_upgrade_charm(self, event):
        logging.info('UPGRADE')
        self.on.config_changed.emit()

    def on_leader_elected(self, event):
        logging.info('LEADER ELECTED')
        self.on.config_changed.emit()

    def getUnits(self):
        logging.info('get_units')
        peer_relation = self.model.get_relation('cluster')
        units = self._unit
        if peer_relation is not None:
            logging.info(peer_relation)
            if not self.model.config['ha-mode']:
                self._unit = 1
            else:
                self._unit =  len(peer_relation.units) + 1
        self.on.update_status.emit()

    def on_cluster_modified(self, event):
        logging.info('on_cluster_modified')
        self.on.config_changed.emit()

    def on_update_status(self, event):
        logging.info('UPDATE STATUS')
        if self._pod.is_ready:
            logging.info('Pod is ready')
            self.state.isStarted = True
            if (self.model.pod._backend.is_leader()):
                self.model.unit.status = ActiveStatus('ready')
            else:
                self.model.unit.status = ActiveStatus('ready Not a Leader')

    def on_config_changed(self, event):
        logging.info('CONFIG CHANGED')
        if self._pod.is_ready:
            if (self.model.pod._backend.is_leader()):
                self.getUnits()
                podSpec = self.makePodSpec()
                if self.state.podSpec != podSpec:
                    self.model.pod.set_spec(podSpec)
                    self.state.podSpec = podSpec
        self.on.update_status.emit()

    def on_new_client(self, event):
        logging.info('NEW CLIENT')
        if not self.state.isStarted:
            logging.info('NEW CLIENT DEFERRED')
            return event.defer()
        logging.info('NEW CLIENT SERVING')
        if (self.model.pod._backend.is_leader()):
            self.client.expose_zookeeper()

    def makePodSpec(self):
        logging.info('MAKING POD SPEC')
        with open("templates/spec_template.yaml") as spec_file:
            podSpecTemplate = spec_file.read()
        dockerImage = self.model.config['image']
        logging.info(self._unit)
        data = {
            "name": self.model.app.name,
            "zookeeper-units": int(self._unit),
            "docker_image_path": dockerImage,
            "server-port": self.model.config['server-port'],
            "client-port": self.model.config['client-port'],
            "leader-election-port": int(self.model.config['leader-election-port']),
        }
        logging.info(data)
        podSpec = podSpecTemplate % data
        podSpec = yaml.load(podSpec)
        return podSpec

if __name__ == "__main__":
    main(ZookeeperCharm)
