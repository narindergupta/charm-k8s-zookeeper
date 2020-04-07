import ipaddress
import json
import logging

from ops.framework import EventBase, EventSource, StoredState
from ops.framework import Object


class ZookeeperCluster(Object):

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self._relation_name = relation_name
        self._listen_address = None
        self._ingress_address = None

    @property
    def is_joined(self):
        return self.framework.model.get_relation(self._relation_name) is not None

    @property
    def relation(self):
        return self.framework.model.get_relation(self._relation_name)

    @property
    def peer_addresses(self):
        addresses = []
        relation = self.relation
        if relation:
            for u in relation.units:
                addresses.append(relation.data[u]['ingress-address'])
        return addresses

    @property
    def listen_address(self):
        if self._listen_address is None:
            self._listen_address = self.model.get_binding(self._relation_name).network.bind_address
        return self._listen_address

    @property
    def ingress_address(self):
        if self._ingress_address is None:
            self._ingress_address = self.model.get_binding(self._relation_name).network.ingress_address
        return self._ingress_address

    def init_state(self, event):
        self.state.apps = []
        pass


class ZookeeperClient(Object):

    state = StoredState()

    def __init__(self, charm, relation_name, client_port):
        super().__init__(charm, relation_name)
        self._relation_name = relation_name
        self._client_port = client_port
        self._listen_address = None
        self._ingress_addresses = None
        self.state.set_default(host=None, port=None, rest_port=None)

    @property
    def listen_address(self):
        if self._listen_address is None:
            addresses = set()
            for relation in self.model.relations[self._relation_name]:
                address = self.model.get_binding(relation).network.bind_address
                addresses.add(address)
            if len(addresses) > 1:
                raise Exception('Multiple potential listen addresses detected: Zookeeper does not support that')
            elif addresses == 1:
                self._listen_address = addresses.pop()
            else:
                # Default to network information associated with an endpoint binding itself in absence of relations.
                self._listen_address = self.model.get_binding(self._relation_name).network.bind_address
        return self._listen_address

    def set_host(self, host):
        self.state.host = host

    def set_port(self, port):
        self.state.port = port

    def set_rest_port(self, rest_port):
        self.state.rest_port = rest_port

    def expose_zookeeper(self):
        rel = self.model.get_relation(self._relation_name)
        logging.info({
                      'host': self.state.host,
                      'port': self.state.port,
                      'rest_port': self.state.rest_port
                    })
        if rel is not None:
            if self.model.unit.is_leader() and self.state.host is not None:
                rel.data[self.model.unit]['host'] = self.state.host
                rel.data[self.model.unit]['port'] = str(self.state.port)
                rel.data[self.model.unit]['rest_port'] = str(self.state.rest_port)

    @property
    def ingress_addresses(self):
        # Even though NATS does not support multiple listening addresses that does not mean there
        # cannot be multiple ingress addresses clients would use.
        if self._ingress_addresses is None:
            self._ingress_addresses = set()
            for relation in self.model.relations[self._relation_name]:
                self._ingress_addresses.add(self.model.get_binding(relation).network.ingress_address)
        return self._ingress_addresses
