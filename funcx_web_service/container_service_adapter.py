from urllib.parse import urljoin

import requests


class ContainerServiceAdapter:
    def __init__(self, service_url):
        self.service_url = service_url

    def get_version(self):
        result = requests.get(urljoin(self.service_url, "version"))
        if result.status_code == 200:
            return result.json()
        else:
            return {"version": "Service Unavailable"}
