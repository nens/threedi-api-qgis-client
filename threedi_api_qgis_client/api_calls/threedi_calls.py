import os
from threedi_api_client import ThreediApiClient
from openapi_client.exceptions import ApiException
from openapi_client.api.statuses_api import StatusesApi
from openapi_client.api.repositories_api import RepositoriesApi


class ThreediCalls:
    """Class to do all the communication with the 3Di API."""

    def __init__(self, api_host, api_username, api_password):
        """
        Setup open_api client using username and password.
        """
        os.environ["API_HOST"] = api_host
        os.environ["API_USERNAME"] = api_username
        os.environ["API_PASSWORD"] = api_password
        self.api_host = api_host
        self.api_username = api_username
        self.api_client = ThreediApiClient()
        self._config = self.api_client.configuration
        self._token = self._config.access_token

    def get_repositories_list(self):
        ra = RepositoriesApi(self.api_client)
        repositories_list = ra.repositories_list()  # Need to add ApiException handling here
        return repositories_list


if __name__ == "__main__":
    import sys
    API_HOST = "https://api.3di.live/v3.0"
    API_USERNAME = sys.argv[1]
    API_PASSWORD = sys.argv[2]
    tc = ThreediCalls(API_HOST, API_USERNAME, API_PASSWORD)
    repos = tc.get_repositories_list()
    print(repos)
