#!/usr/bin/env python3

import sys
import json
import subprocess
sys.path.append('lib')

from ops.charm import CharmBase, CharmEvents
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

from interface import Zookeeper
from k8s import K8sPod

import logging
import subprocess

import yaml

logging.basicConfig(level=logging.DEBUG)

class ZookeeperCharm(CharmBase):
    state = StoredState()

    def __init__(self, framework, key):
        super().__init__(framework, key)
        self.__unit = 1
        self.state.set_default(isStarted=False)
        self.zookeeper = Zookeeper(self, 'zookeeper')
        self.zookeepercluster = Zookeeper(self, 'cluster')
        self._pod = K8sPod(self.framework.model.app.name)

        self.framework.observe(self.on.start, self)
        self.framework.observe(self.on.stop, self)
        self.framework.observe(self.on.update_status, self)
        self.framework.observe(self.on.config_changed, self)
        self.framework.observe(self.on.upgrade_charm, self)
        self.framework.observe(self.on.leader_elected, self)
        self.framework.observe(self.on.zookeeper_relation_joined, self)
        self.framework.observe(self.on.zookeeper_relation_changed, self)
        self.framework.observe(self.on.zookeeper_relation_departed, self)
        self.framework.observe(self.on.zookeeper_relation_broken, self)
        self.framework.observe(self.zookeeper.on.new_client, self)
        self.framework.observe(self.on.cluster_relation_changed, self.on_cluster_modified)

    def on_start(self, event):
        logging.info('START')
        self.model.unit.status = MaintenanceStatus('Configuring pod')
        if (self.model.pod._backend.is_leader()):
#        if not self.model.config['ha-mode']:
            podSpec = self.makePodSpec()
            self.model.pod.set_spec(podSpec)
            self.state.podSpec = podSpec
            if self._pod.is_ready:
                self.state.isStarted = True
                self.model.unit.status = ActiveStatus('ready')
                logging.info('Pod is ready')
                return
            self.model.unit.status = MaintenanceStatus('Pod is not ready')
            logging.info('Pod is not ready')

    def on_stop(self, event):
        logging.info('STOP')

    def on_upgrade_charm(self, event):
        logging.info('UPGRADE')
        self.on.config_changed.emit()

    def getUnits(self):
        logging.info('get_units')
        peer_relation = self.model.get_relation('cluster')
        units = self.__unit
        if peer_relation is not None:
            logging.info(peer_relation)
            if not self.model.config['ha-mode']:
                self.__unit = 1
            else:
                self.__unit =  len(peer_relation.units) + 1
        if self.__unit != units:
            self.on.config_changed.emit()

    def on_cluster_modified(self, event):
        logging.info('on_cluster_modified')
        self.getUnits()

    def on_update_status(self, event):
        logging.info('UPDATE STATUS')
        if (self.model.pod._backend.is_leader()):
            if self._pod.is_ready:
                self.model.unit.status = ActiveStatus('ready')
        else:
            if self._pod.is_ready:
                self.model.unit.status = ActiveStatus('ready Not a Leader')
        relation = self.model.get_relation('zookeeper')
        if relation is not None:
            logging.info(relation.data[self.model.unit].get('host'))

    def on_config_changed(self, event):
        logging.info('CONFIG CHANGED')
        self.model.unit.status = ActiveStatus('config changed')
        if (self.model.pod._backend.is_leader()):
            self.getUnits()
            podSpec = self.makePodSpec()
            if self.state.podSpec != podSpec:
                self.model.unit.status = MaintenanceStatus('Configuring pod')
                self.model.pod.set_spec(podSpec)
                self.state.podSpec = podSpec
            if self._pod.is_ready:
                self.state.isStarted = True
                self.model.unit.status = ActiveStatus('ready')
        else:
            if self._pod.is_ready:
                self.state.isStarted = True
                self.model.unit.status = ActiveStatus('ready Not a Leader')

    def on_leader_elected(self, event):
        logging.info('LEADER ELECTED')

    def on_zookeeper_relation_joined(self, event):
        logging.info('zookeeper RELATION JOINED')

    def on_zookeeper_relation_changed(self, event):
        logging.info('zookeeper RELATION CHANGED')

    def on_zookeeper_relation_departed(self, event):
        logging.info('zookeeper RELATION DEPARTED')

    def on_zookeeper_relation_broken(self, event):
        logging.info('zookeeper RELATION BROKEN')

    def on_new_client(self, event):
        logging.info('NEW CLIENT')
        if not self.state.isStarted:
            logging.info('NEW CLIENT DEFERRED')
            return event.defer()
        logging.info('NEW CLIENT SERVING')
        event.client.serve(
                           host=event.client.ingress_address,
                           port=self.model.config['client-port'],
                           rest_port=self.model.config['client-port'])

    def makePodSpec(self):
        logging.info('MAKING POD SPEC')
        with open("templates/spec_template.yaml") as spec_file:
            podSpecTemplate = spec_file.read()
        dockerImage = self.model.config['image']
        logging.info(self.__unit)
        data = {
            "name": self.model.app.name,
            "zookeeper-units": int(self.__unit),
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
