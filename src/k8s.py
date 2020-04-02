#!/usr/bin/env python3
import json
import http.client
import os
import ssl
import logging

logger = logging.getLogger()


class K8sApi:

    def get(self, path):
        return self.request('GET', path)

    def request(self, method, path):
        with open("/var/run/secrets/kubernetes.io/serviceaccount/token") \
                as token_file:
            kube_token = token_file.read()

        ssl_context = ssl.SSLContext()
        ssl_context.load_verify_locations(
            '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')

        headers = {
            'Authorization': f'Bearer {kube_token}'
        }

        conn = http.client.HTTPSConnection('kubernetes.default.svc',
                                           context=ssl_context)
        conn.request(method=method, url=path, headers=headers)
        raw_response = conn.getresponse().read()
        #logger.info("Conn.getresponse: {}".format(raw_response))

        return json.loads(raw_response)


class K8sPod:

    def __init__(self, app_name):
        self._app_name = app_name
        self._status = None

    def fetch(self):
        namespace = os.environ["JUJU_MODEL_NAME"]

        path = f'/api/v1/namespaces/{namespace}/pods?'\
               f'labelSelector=juju-app={self._app_name}'

        api_server = K8sApi()
        response = api_server.get(path)
        #logger.info("K8sApiServer response: {}".format(response))

        if response.get('kind', '') == 'PodList' and response['items']:
            unit = os.environ['JUJU_UNIT_NAME']
            status = next(
                (i for i in response['items']
                 if i['metadata']['annotations'].get('juju.io/unit') == unit),
                None
            )
        else:
            status = None

        #logger.info("K8sPod status: {}".format(status))
        self._status = status

    @property
    def is_ready(self):
        if not self._status:
            self.fetch()
        if not self._status:
            return False
        return next(
            (
                condition['status'] == "True" for condition
                in self._status['status']['conditions']
                if condition['type'] == 'ContainersReady'
            ),
            False
        )

    @property
    def is_running(self):
        if not self._status:
            self.fetch()
        if not self._status:
            return False
        return self._status['status']['phase'] == 'Running'
