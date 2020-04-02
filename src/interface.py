import json

from ops.framework import EventBase, EventsBase, EventSource, Object, StoredState

import logging

class NewClient(EventBase):
    def __init__(self, handle, client):
        super().__init__(handle)
        self.client = client

    def snapshot(self):
        return {
            'relation_name': self.client._relation.name,
            'relation_id': self.client._relation.id,
        }

    def restore(self, snapshot):
        relation = self.framework.model.get_relation(snapshot['relation_name'], snapshot['relation_id'])
        self.client = ZookeeperInterfaceClient(relation, self.framework.model.unit)


class ZookeeperEvents(EventsBase):
    new_client = EventSource(NewClient)


class Zookeeper(Object):
    on = ZookeeperEvents()
    state = StoredState()
    unit = 1

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.framework.observe(charm.on.start, self.init_state)
        self.framework.observe(charm.on[relation_name].relation_joined, self.on_joined)
        self.framework.observe(charm.on[relation_name].relation_departed, self.on_departed)


    def init_state(self, event):
        self.state.apps = []
        pass

    @property
    def _relations(self):
        return self.model.relations[self.relation_name]

    def on_joined(self, event):
        logging.info('on_joined:')
        if event.app.name not in self.state.apps:
            self.state.apps.append(event.app.name)
            self.on.new_client.emit(ZookeeperInterfaceClient(event.relation, self.model.unit))

    def on_departed(self, event):
        logging.info('on_departed:')
        self.state.apps = [app.name for app in self._relations]
        pass

    def clients(self):
        logging.info('clients:')
        return [ZookeeperInterfaceClient(relation, self.model.unit) for relation in self._relations]

class ZookeeperInterfaceClient:
    def __init__(self, relation, local_unit):
        self._relation = relation
        self._local_unit = local_unit
        self.ingress_address = relation.data[local_unit]['ingress-address']

    def serve(self, host, port, rest_port):
        logging.info('ZookeeperInterfaceClient DATA:')
        logging.info({
                      'host': host,
                      'port': port,
                      'rest_port': rest_port
                    })
        self._relation.data[self._local_unit]['host'] = host
        self._relation.data[self._local_unit]['port'] = str(port)
        self._relation.data[self._local_unit]['rest_port'] = str(rest_port)
