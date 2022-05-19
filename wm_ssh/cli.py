#!/usr/bin/env python3
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import requests

LOGGER = logging.getLogger("wm-ssh" if __name__ == "__main__" else __name__)
DEFAULT_CONFIG_PATH = Path("~/.config/netbox/config.json").expanduser()
DEFAULT_CACHE_PATH = Path("~/.cache/wm-ssh").expanduser()
DEFAULT_CONFIG = {
    "netbox_url": "https://netbox.local/api",
    "api_token": "IMADUMMYTOKEN",
}


@dataclass
class CacheFile:
    path: Path

    def search_host(self, partial_host: str) -> Optional[str]:
        if self.path.exists():
            all_hosts = self.path.read_text().splitlines()
            for maybe_host in all_hosts:
                if maybe_host.startswith(partial_host):
                    return maybe_host

        return None

    def add_host(self, full_hostname: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.search_host(partial_host=full_hostname):
            return

        with self.path.open("a") as cache_fd:
            cache_fd.write(f"{full_hostname}\n")

    def replace_content(self, new_content: str) -> None:
        self.path.write_text(data=new_content)


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


def _remove_duplicated_key_if_needed(stderr: str) -> bool:
    if "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED" in stderr:
        if click.confirm("The host key has changed, remove the old one and retry?", err=True):
            remove_key_command = None
            next = False
            for line in stderr.splitlines():
                if next:
                    remove_key_command = line
                    break
                if line.strip().startswith("remove with:"):
                    next = True

            if remove_key_command is not None:
                subprocess.check_output(["/bin/bash", "-c", remove_key_command.strip()])
                return True
            else:
                raise Exception("Unable to find the command to remove a key from the output: \n{stderr}")

    return False


def try_ssh(hostname: str, cachefile: Optional[CacheFile], user: str = None) -> Optional[str]:
    LOGGER.debug("[direct] Trying hostname %s@%s", user or "nouser", hostname)
    if cachefile:
        maybe_host = cachefile.search_host(hostname)
        if maybe_host:
            LOGGER.debug("[direct] Got host %s from the cache", maybe_host)
            return maybe_host

    res = subprocess.run(args=["ssh", user and f"{user}@{hostname}" or hostname, "hostname"], capture_output=True)
    if res.returncode == 0:
        LOGGER.debug("[direct] Hostname %s worked", hostname)
        if cachefile:
            LOGGER.debug("[direct] Adding %s in the cache", hostname)
            cachefile.add_host(full_hostname=hostname)

        return hostname

    if "Could not resolve hostname" in res.stderr.decode():
        LOGGER.debug("[direct] Hostname %s was unresolved", hostname)
        return None

    if _remove_duplicated_key_if_needed(stderr=res.stderr.decode()):
        return try_ssh(hostname=hostname, user=user, cachefile=cachefile)

    raise Exception(
        f"Unknown error when trying to ssh to {hostname}: \nstdout:\n{res.stdout.decode()}\n"
        f"stderr:\n{res.stderr.decode()}"
    )


def get_host_from_netbox(config: Dict[str, Any], hostname: str, cachefile: Optional[CacheFile]) -> Optional[str]:
    if cachefile:
        maybe_host = cachefile.search_host(hostname)
        if maybe_host:
            return maybe_host

    full_hostname = get_physical(
        netbox_url=config["netbox_url"],
        api_token=config["api_token"],
        search_query=hostname,
    )
    LOGGER.debug("netbox: found physical host %s", full_hostname)
    if not full_hostname:
        full_hostname = get_vm(
            netbox_url=config["netbox_url"],
            api_token=config["api_token"],
            search_query=hostname,
        )
        LOGGER.debug("netbox: found vm: %s", full_hostname)

    if cachefile and full_hostname:
        cachefile.add_host(full_hostname=full_hostname)

    return full_hostname


def get_host_from_openstackbrowser(hostname: str, cachefile: Optional[CacheFile]) -> Optional[str]:
    if cachefile:
        maybe_vm = cachefile.search_host(hostname)
        if maybe_vm:
            return maybe_vm

    all_vms_response = requests.get("https://openstack-browser.toolforge.org/api/dsh/servers")
    all_vms_response.raise_for_status()
    if cachefile:
        cachefile.replace_content(all_vms_response.text)
        return cachefile.search_host(hostname)

    for maybe_vm in all_vms_response.text.splitlines():
        if maybe_vm.startswith(hostname):
            return maybe_vm.strip()

    return None


@click.command(name="wm-ssh", help="Wikimedia ssh wrapper that expands hostnames")
@click.option("-v", "--verbose", help="Show extra verbose output", is_flag=True)
@click.option(
    "--netbox-config-file",
    default=str(DEFAULT_CONFIG_PATH),
    help="Path to the configuration file with the netbox settings.",
)
@click.option(
    "--no-caches", help="Ignore the caches, this does not remove them, only ignores them for the run.", is_flag=True
)
@click.option("--flush-caches", help="Clean the caches, this removes any cached hosts.", is_flag=True, default=False)
@click.argument("hostname")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def wm_ssh(
    verbose: bool, hostname: str, netbox_config_file: str, no_caches: bool, flush_caches: bool, args: List[str]
) -> None:
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    LOGGER.debug("Loading config file from %s", netbox_config_file)
    config = load_config_file(config_path=netbox_config_file)
    LOGGER.debug("Config file loaded from %s", netbox_config_file)
    netbox_cachefile = CacheFile(path=DEFAULT_CACHE_PATH / "netbox.txt")
    openstack_cachefile = CacheFile(path=DEFAULT_CACHE_PATH / "openstackbrowser.txt")
    direct_cachefile = CacheFile(path=DEFAULT_CACHE_PATH / "direct.txt")

    if flush_caches and click.confirm("This will erase the caches permanently, are you sure?"):
        netbox_cachefile.replace_content("")
        openstack_cachefile.replace_content("")
        direct_cachefile.replace_content("")

    if no_caches:
        netbox_cachefile = None
        openstack_cachefile = None
        direct_cachefile = None

    if "@" in hostname:
        user, hostname = hostname.split("@", 1)
    else:
        user = None

    full_hostname = try_ssh(hostname, cachefile=direct_cachefile, user=user)
    if not full_hostname:
        LOGGER.debug("Trying netbox with %s", hostname)
        try:
            full_hostname = get_host_from_netbox(config=config, hostname=hostname, cachefile=netbox_cachefile)
        except Exception as error:
            LOGGER.warning(f"Got error when trying to fetch host from netbox: {error}")

        if not full_hostname:
            LOGGER.debug("Trying openstack browser with %s", hostname)
            try:
                full_hostname = (
                    get_host_from_openstackbrowser(hostname=hostname, cachefile=openstack_cachefile) or hostname
                )
            except Exception as error:
                LOGGER.warning(f"Got error when trying to fetch host from openstackbrowser: {error}")

    if not full_hostname:
        LOGGER.error("Unable to find a hostname for '%s'", full_hostname)
        sys.exit(1)

    LOGGER.info("Found full hostname %s", full_hostname)
    if user:
        full_hostname = f"{user}@{full_hostname}"

    LOGGER.debug("Waiting for ssh to finish...")
    _do_ssh(full_hostname=full_hostname, args=args)
    LOGGER.debug("Done")


def _do_ssh(full_hostname: str, args: List[str]) -> None:
    cmd = ["ssh", full_hostname, *args]
    proc = subprocess.Popen(args=cmd, bufsize=0, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, shell=False)
    proc.wait()
    if proc.returncode != 0:
        LOGGER.debug("First attempt failed with error, rerunning dummy ssh to get output...")
        capturing_proc = subprocess.run(args=["ssh", full_hostname, "hostname"], capture_output=True)
        if _remove_duplicated_key_if_needed(stderr=capturing_proc.stderr.decode()):
            LOGGER.debug("Found and removed duplicated key, retrying...")
            return _do_ssh(full_hostname=full_hostname, args=args)

        else:
            raise subprocess.CalledProcessError(returncode=proc.returncode, output=None, stderr=None, cmd=cmd)


if __name__ == "__main__":
    wm_ssh()
