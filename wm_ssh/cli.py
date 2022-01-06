#!/usr/bin/env python3
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import requests

LOGGER = logging.getLogger("wm-ssh" if __name__ == "__main__" else __name__)
DEFAULT_CONFIG_PATH = Path("~/.config/netbox/config.json").expanduser()
DEFAULT_CONFIG = {
    "netbox_url": "https://netbox.local/api",
    "api_token": "IMADUMMYTOKEN",
}


def get_fqdn(
    api_token: str,
    device: Dict[str, Any],
) -> Optional[str]:
    if device["primary_ip"]:
        response = requests.get(
            url=device["primary_ip"]["url"],
            headers={"Authorization": f"Token {api_token}"},
        )
        response.raise_for_status()
        ip_info = response.json()
        dns_name = ip_info["dns_name"]
        if dns_name:
            return dns_name

    return f"{device['name']}.{device['site']['slug']}.wmnet"


def get_vm(
    netbox_url: str,
    api_token: str,
    search_query: str,
) -> Optional[str]:
    response = requests.get(
        url=f"{netbox_url}/virtualization/virtual-machines/",
        params={"q": search_query},
        headers={"Authorization": f"Token {api_token}"},
    )
    response.raise_for_status()
    vm_infos = response.json()["results"]
    for vm_info in vm_infos:
        fqdn = get_fqdn(
            api_token,
            device=vm_info,
        )
        if fqdn:
            return fqdn

    return None


def get_physical(
    netbox_url: str,
    api_token: str,
    search_query: str,
) -> Optional[str]:
    response = requests.get(
        url=f"{netbox_url}/dcim/devices/",
        params={"q": search_query},
        headers={"Authorization": f"Token {api_token}"},
    )
    response.raise_for_status()
    machine_infos = response.json()["results"]
    for machine_info in machine_infos:
        fqdn = get_fqdn(
            api_token,
            device=machine_info,
        )
        if fqdn:
            return fqdn

    return None


def load_config_file(config_path: str = str(DEFAULT_CONFIG_PATH)) -> Dict[str, str]:
    return json.load(open(config_path))


def try_ssh(hostname: str):
    LOGGER.debug("Trying hostname %s", hostname)
    res = subprocess.run(args=["ssh", hostname, "hostname"], capture_output=True)
    if res.returncode == 0:
        LOGGER.debug("Hostname %s worked", hostname)
        return True

    if "Could not resolve hostname" in res.stderr.decode():
        LOGGER.debug("Hostname %s was unresolved", hostname)
        return False

    raise Exception(
        f"Unknown error when trying to ssh to {hostname}: \nstdout:\n{res.stdout.decode()}\n"
        f"stderr:\n{res.stderr.decode()}"
    )


def get_host_from_netbox(config: Dict[str, Any], hostname: str) -> Optional[str]:
    full_hostname = get_physical(
        netbox_url=config["netbox_url"],
        api_token=config["api_token"],
        search_query=hostname,
    )
    if not full_hostname:
        full_hostname = get_vm(
            netbox_url=config["netbox_url"],
            api_token=config["api_token"],
            search_query=hostname,
        )

    return full_hostname


@click.command(name="wm-ssh", help="Wikimedia ssh wrapper that expands hostnames")
@click.option("-v", "--verbose", help="Show extra verbose output", is_flag=True)
@click.option(
    "--netbox-config-file",
    default=str(DEFAULT_CONFIG_PATH),
    help="Path to the configuration file with the netbox settings.",
)
@click.argument("hostname")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def wm_ssh(verbose: bool, hostname: str, netbox_config_file: str, args: List[str]) -> None:
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    LOGGER.debug("Loading config file from %s", netbox_config_file)
    config = load_config_file(config_path=netbox_config_file)
    LOGGER.debug("Config file loaded from %s", netbox_config_file)

    if try_ssh(hostname):
        full_hostname = hostname
    else:
        LOGGER.debug("Trying netbox with %s", hostname)
        full_hostname = get_host_from_netbox(config=config, hostname=hostname) or hostname

    LOGGER.info("Found full hostname %s", full_hostname)
    cmd = ["ssh", full_hostname, *args]
    proc = subprocess.Popen(args=cmd, bufsize=0, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, shell=False)
    LOGGER.debug("Waiting for ssh to finish...")
    proc.wait()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(returncode=proc.returncode, output=None, stderr=None, cmd=cmd)

    LOGGER.debug("Done")


if __name__ == "__main__":
    wm_ssh()
