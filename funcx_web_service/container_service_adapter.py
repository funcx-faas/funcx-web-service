from urllib.parse import urljoin

import requests

from funcx import ContainerSpec


class ContainerServiceAdapter:
    def __init__(self, service_url):
        self.service_url = service_url

    def get_version(self):
        result = requests.get(urljoin(self.service_url, "version"))
        if result.status_code == 200:
            return result.json()
        else:
            return {"version": "Service Unavailable"}

    def submit_build(self, container_id: str, container_spec: dict):
        build_request = {
            "container_type": "Docker",
            "container_id": container_id,
            "apt": container_spec["apt"],
            "pip": container_spec["pip"],
            "conda": container_spec["conda"]
        }
        result = requests.post(urljoin(self.service_url, "build"),
                               json=build_request)
        print(result)