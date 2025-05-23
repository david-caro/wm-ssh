#!/usr/bin/env python3
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, TextIO

import click
import requests

LOGGER = logging.getLogger("wm-ssh" if __name__ == "__main__" else __name__)
LOCAL_KNOWN_HOSTS = Path("~/.ssh/known_hosts").expanduser()
DEFAULT_CONFIG_PATH = Path("~/.config/wm-ssh/config.json").expanduser()
DEFAULT_CACHE_PATH = Path("~/.cache/wm-ssh").expanduser()
DEFAULT_CONFIG = {
    "netbox_config_path": "~/.config/netbox/config.json",
    "known_hosts_url": "https://config-master.wikimedia.org/known_hosts.ecdsa",
    "openstack_browser_url": "https://openstack-browser.toolforge.org/api/dsh/servers",
}
EXAMPLE_NETBOX_CONFIG = {
    "netbox_url": "https://netbox.local/api",
    "api_token": "IMADUMMYTOKEN",
}


@dataclass
class CacheFile:
    path: Path

    def __post_init__(self):
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def search_host(self, partial_host: str) -> str | None:
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

    def remove_host(self, full_hostname: str) -> None:
        old_content = self.path.open().read()
        new_content = old_content.replace(f"{full_hostname}\n", "")
        self.path.open("w").write(new_content)

    def replace_content(self, new_content: str) -> None:
        self.path.write_text(data=new_content)


def in_known_hosts(hostname: str) -> bool:
    hostline = re.compile(f"^{hostname} ")
    return any(hostline.match(line) for line in LOCAL_KNOWN_HOSTS.open())


def remove_from_known_hosts(hostname: str) -> None:
    subprocess.run(
        args=["ssh-keygen", "-R", hostname],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class Resolver:
    def get_host(self, hostname: str) -> str | None:
        raise NotImplementedError("This method should be overridden in subclasses.")


@dataclass
class NetboxResolver(Resolver):
    api_token: str
    netbox_url: str
    cachefile: CacheFile | None

    def get_fqdn(
        self,
        device: Dict[str, Any],
    ) -> str | None:
        if device["primary_ip"]:
            response = requests.get(
                url=device["primary_ip"]["url"],
                headers={"Authorization": f"Token {self.api_token}"},
            )
            response.raise_for_status()
            ip_info = response.json()
            dns_name = ip_info["dns_name"]
            if dns_name:
                return dns_name

        return f"{device['name']}.{device['site']['slug']}.wmnet"

    def get_vm(
        self,
        search_query: str,
    ) -> str | None:
        response = requests.get(
            url=f"{self.netbox_url}/virtualization/virtual-machines/",
            params={"q": search_query},
            headers={"Authorization": f"Token {self.api_token}"},
        )
        response.raise_for_status()
        vm_infos = response.json()["results"]
        for vm_info in vm_infos:
            fqdn = self.get_fqdn(device=vm_info)
            if fqdn:
                return fqdn

        return None

    def get_physical(
        self,
        search_query: str,
    ) -> str | None:
        response = requests.get(
            url=f"{self.netbox_url}/dcim/devices/",
            params={"q": search_query},
            headers={"Authorization": f"Token {self.api_token}"},
        )
        response.raise_for_status()
        machine_infos = response.json()["results"]
        for machine_info in machine_infos:
            fqdn = self.get_fqdn(device=machine_info)
            if fqdn:
                return fqdn

        return None

    def get_host(self, hostname: str) -> str | None:
        if self.cachefile:
            maybe_host = self.cachefile.search_host(hostname)
            if maybe_host:
                return maybe_host

        full_hostname = self.get_physical(search_query=hostname)
        LOGGER.debug("netbox: found physical host %s", full_hostname)
        if not full_hostname:
            full_hostname = self.get_vm(search_query=hostname)
            LOGGER.debug("netbox: found vm: %s", full_hostname)

        if self.cachefile and full_hostname:
            self.cachefile.add_host(full_hostname=full_hostname)

        return full_hostname

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return f"NetboxResolver(api_token=*******, netbox_url='{self.netbox_url}', cache_file='{self.cachefile}')"


@dataclass
class OpenstackBrowserResolver(Resolver):
    openstack_browser_url: str
    cachefile: CacheFile | None

    def get_host(self, hostname: str) -> str | None:
        if self.cachefile:
            maybe_vm = self.cachefile.search_host(hostname)
            if maybe_vm:
                return maybe_vm

        all_vms_response = requests.get(self.openstack_browser_url)
        all_vms_response.raise_for_status()
        if self.cachefile:
            self.cachefile.replace_content(all_vms_response.text)
            return self.cachefile.search_host(hostname)

        for maybe_vm in all_vms_response.text.splitlines():
            if maybe_vm and maybe_vm.startswith(hostname):
                return maybe_vm.strip()

        return None


@dataclass
class KnownHostsResolver(Resolver):
    known_hosts_url: str
    cachefile: CacheFile | None

    def get_host(self, hostname: str) -> str | None:
        if self.cachefile:
            maybe_known_host = self.cachefile.search_host(hostname)
            if maybe_known_host:
                return maybe_known_host

        all_known_hosts_response = requests.get(self.known_hosts_url)
        all_known_hosts_response.raise_for_status()
        clean_hosts = [host_line.split(",", 1)[0] for host_line in all_known_hosts_response.text.splitlines()]
        if self.cachefile:
            self.cachefile.replace_content("\n".join(clean_hosts))
            return self.cachefile.search_host(hostname)

        for maybe_known_host in clean_hosts:
            if maybe_known_host and maybe_known_host.startswith(hostname):
                return maybe_known_host.strip()

        return None


def load_config_file(config_path: Path) -> Dict[str, Any]:
    LOGGER.debug("Loading config file from %s", config_path)
    wm_ssh_config = DEFAULT_CONFIG.copy()
    if config_path.exists():
        wm_ssh_config.update(json.load(config_path.expanduser().open()))
        LOGGER.debug("Config file loaded from %s", config_path)
    else:
        LOGGER.debug("Config file '%s' not found, using default config.", config_path)

    if (
        wm_ssh_config.get("netbox_config_path", None)
        and Path(wm_ssh_config["netbox_config_path"]).expanduser().exists()
    ):
        netbox_config = json.load(Path(wm_ssh_config["netbox_config_path"]).expanduser().open())
        wm_ssh_config["netbox_config"] = netbox_config
        LOGGER.debug("Netbox config file loaded from '%s'", config_path)
    else:
        LOGGER.debug("Unable to load netbox config file '%s'", wm_ssh_config["netbox_config_path"])

    return wm_ssh_config


def _remove_duplicated_key_if_needed(stderr: str, hostname: str) -> bool:
    if "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED" not in stderr:
        return False

    if not click.confirm("The host key has changed, remove the old one and retry?", err=True):
        return False

    remove_from_known_hosts(hostname)
    return True


def try_ssh(hostname: str, cachefile: CacheFile | None, user: str | None = None) -> str | None:
    from_cache = False
    LOGGER.debug("[direct] Looking up hostname %s%s", f"{user}@" if user else "", hostname)
    if cachefile:
        maybe_host = cachefile.search_host(hostname)
        if maybe_host:
            LOGGER.debug("[direct] Got host %s from the cache", maybe_host)
            hostname = maybe_host
            from_cache = True

    res = subprocess.run(
        args=["ssh", f"{user}@{hostname}" if user else hostname, "hostname"],
        capture_output=True,
    )
    if res.returncode == 0:
        LOGGER.debug("[direct] Hostname %s worked", hostname)
        if cachefile:
            LOGGER.debug("[direct] Adding %s in the cache", hostname)
            cachefile.add_host(full_hostname=hostname)

        return hostname

    if any(
        msg in res.stderr.decode()
        for msg in ("Could not resolve hostname", "Name or service not known", "No route to host")
    ):
        LOGGER.info("Hostname %s unresolved", hostname)
        if from_cache:
            if click.confirm("Do you want to remove it from the cache?", default=False):
                if cachefile:
                    cachefile.remove_host(hostname)
                remove_from_known_hosts(hostname)
                LOGGER.info("Host %s removed from cache, will not autosuggest again.", hostname)
                sys.exit(1)

            raise Exception(f"Unable to resolve host {hostname}")

        if in_known_hosts(hostname):
            if click.confirm("Host found in known_hosts, should I remove it from there?", default=False):
                remove_from_known_hosts(hostname)
                LOGGER.info("Host %s removed from known_hosts, will not autosuggest again.", hostname)
                sys.exit(1)

            raise Exception(f"Unable to resolve host {hostname}")

        return None

    if _remove_duplicated_key_if_needed(stderr=res.stderr.decode(), hostname=hostname):
        return try_ssh(hostname=hostname, user=user, cachefile=cachefile)

    raise Exception(
        f"Unknown error when trying to ssh to {hostname}: \nstdout: \n{res.stdout.decode()}\n"
        f"stderr: \n{res.stderr.decode()}"
    )


@click.command(
    name="wm-ssh",
    help="Wikimedia ssh wrapper that expands hostnames",
    epilog=(
        "Note that any options to ssh have to be passed after the hostname (ex. wm-ssh dummy-host -D 127.0.0.1:8080)"
    ),
    context_settings={"ignore_unknown_options": True},
)
@click.option("-v", "--verbose", help="Show extra verbose output", is_flag=True)
@click.option("--print-config", help="Show the loaded configuration", is_flag=True)
@click.option("--print-example-config", help="Show a full configuration example", is_flag=True)
@click.option(
    "--config-file",
    default=Path(str(DEFAULT_CONFIG_PATH)),
    help="Path to the configuration file with the wm-ssh settings.",
    type=Path,
)
@click.option(
    "--no-caches", help="Ignore the caches, this does not remove them, only ignores them for the run.", is_flag=True
)
@click.option("--flush-caches", help="Clean the caches, this removes any cached hosts.", is_flag=True, default=False)
@click.argument("hostname", required=False, default=None)
@click.argument("sshargs", nargs=-1, type=click.UNPROCESSED)
def wm_ssh(
    verbose: bool,
    print_config: bool,
    print_example_config: bool,
    hostname: str,
    config_file: Path,
    no_caches: bool,
    flush_caches: bool,
    sshargs: List[str],
) -> int:
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if print_example_config:
        print(f"# You can create a file under {config_file} with this content filling up the fields: ")
        print(json.dumps(DEFAULT_CONFIG, indent=4))
        print(
            "\n# And for netbox config (optional), create a file under "
            f"{Path(DEFAULT_CONFIG['netbox_config_path']).expanduser()} with: "
        )
        print(json.dumps(EXAMPLE_NETBOX_CONFIG, indent=4))
        return 0

    config = load_config_file(config_path=Path(config_file))
    if print_config:
        print(json.dumps(config, indent=4))
        return 0

    known_hosts_cachefile = CacheFile(path=DEFAULT_CACHE_PATH / "known_hosts.txt")
    netbox_cachefile: CacheFile = CacheFile(path=DEFAULT_CACHE_PATH / "netbox.txt")
    openstack_cachefile: CacheFile = CacheFile(path=DEFAULT_CACHE_PATH / "openstackbrowser.txt")
    direct_cachefile: CacheFile = CacheFile(path=DEFAULT_CACHE_PATH / "direct.txt")

    if flush_caches and click.confirm("This will erase the caches permanently, are you sure?"):
        netbox_cachefile.replace_content("")
        openstack_cachefile.replace_content("")
        direct_cachefile.replace_content("")
        if not hostname:
            return 0

    if not hostname:
        print("Error: Missing argument 'HOSTNAME'")
        return 1

    resolvers: list[Resolver] = [
        KnownHostsResolver(
            known_hosts_url=config["known_hosts_url"],
            cachefile=known_hosts_cachefile,
        )
    ]
    if not config.get("netbox_config"):
        LOGGER.info("Unable to find netbox config, disabling netbox resolver.")
    else:
        resolvers.append(
            NetboxResolver(
                netbox_url=config["netbox_config"]["netbox_url"],
                api_token=config["netbox_config"]["api_token"],
                cachefile=None if no_caches else netbox_cachefile,
            )
        )

    resolvers.append(
        OpenstackBrowserResolver(
            openstack_browser_url=config["openstack_browser_url"],
            cachefile=None if no_caches else openstack_cachefile,
        )
    )

    if "@" in hostname:
        user, hostname = hostname.split("@", 1)
    else:
        user = None

    try:
        LOGGER.debug("Trying to ssh directly to %s", hostname)
        _do_ssh(full_hostname=f"{user}@{hostname}" if user else hostname, args=sshargs)
        return 0

    except subprocess.CalledProcessError as error:
        LOGGER.debug("Got exception %s", str(error))
        if _remove_duplicated_key_if_needed(stderr=error.stderr, hostname=hostname):
            _do_ssh(full_hostname=f"{user}@{hostname}" if user else hostname, args=sshargs)
            return 0

    except Exception as error:
        LOGGER.debug("Got exception %s", str(error))
        raise

    LOGGER.debug("Direct ssh failed, trying to resolve.")
    LOGGER.debug("Using resolvers: %s", resolvers)
    for resolver in resolvers:
        LOGGER.debug("Trying resolver %s", resolver)
        try:
            full_hostname = resolver.get_host(hostname=hostname)
            if full_hostname:
                break
        except Exception as error:
            LOGGER.warning(f"Got error when trying to fetch host from {resolver}: {error}")

    if not full_hostname or full_hostname == hostname:
        LOGGER.error("Unable to find a working hostname for '%s'", hostname)
        sys.exit(1)

    LOGGER.info("Found full hostname %s", full_hostname)
    if user:
        full_hostname = f"{user}@{full_hostname}"

    LOGGER.debug("Waiting for ssh to finish...")
    try:
        _do_ssh(full_hostname=full_hostname, args=sshargs)
    except subprocess.CalledProcessError as error:
        LOGGER.debug("Got exception %s", str(error))
        if error.stdout:
            print(error.stdout)
        if error.stderr:
            print(error.stderr)
        return error.returncode
    LOGGER.debug("Done")
    return 0


class Tee(TextIO):
    MAX_CAPTURED_STREAM_SIZE = 1024 * 1024 * 1  # 1MB

    def __init__(self, stream: TextIO):
        self.captured_stream = ""
        self.stream = stream

    def write(self, s: str) -> int:
        if len(self.captured_stream) <= self.MAX_CAPTURED_STREAM_SIZE:
            self.captured_stream += s
        return self.stream.write(s)

    def flush(self) -> None:
        self.stream.flush()

    def close(self) -> None:
        self.stream.close()

    def readable(self) -> bool:
        return self.stream.readable()

    def writable(self) -> bool:
        return self.stream.writable()

    def seekable(self) -> bool:
        return self.stream.seekable()

    def read(self, size: int = -1) -> str:
        return self.stream.read(size)

    def readline(self, size: int = -1) -> str:
        return self.stream.readline(size)

    def readlines(self, hint: int = -1) -> List[str]:
        return self.stream.readlines(hint)

    def writelines(self, lines: Iterable[str]) -> None:
        self.stream.writelines(lines)

    def __enter__(self) -> "Tee":
        self.stream.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stream.__exit__(exc_type, exc_value, traceback)

    def __iter__(self) -> Iterator[str]:
        return self.stream.__iter__()

    def __next__(self) -> str:
        return self.stream.__next__()

    def fileno(self) -> int:
        return self.stream.fileno()

    def isatty(self) -> bool:
        return self.stream.isatty()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self.stream.seek(offset, whence)

    def tell(self) -> int:
        return self.stream.tell()

    def truncate(self, size: int | None = None) -> int:
        return self.stream.truncate(size)


def _do_ssh(full_hostname: str, args: List[str]) -> None:
    cmd = ["ssh", full_hostname, *args]
    captured_stdout = Tee(stream=sys.stdout)
    captured_stderr = Tee(stream=sys.stderr)
    try:
        with subprocess.Popen(
            args=cmd, bufsize=0, stdin=sys.stdin, stdout=captured_stdout, stderr=captured_stderr, shell=False
        ) as proc:
            proc.wait()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(
                    returncode=proc.returncode,
                    output=captured_stdout.captured_stream,
                    stderr=captured_stderr.captured_stream,
                    cmd=cmd,
                )

    except subprocess.CalledProcessError as error:
        LOGGER.debug("Got exception %s", str(error))
        if error.stdout:
            print(error.stdout)
        if error.stderr:
            print(error.stderr)
        error.stderr = captured_stderr.captured_stream
        error.stdout = captured_stdout.captured_stream
        raise error


if __name__ == "__main__":
    sys.exit(wm_ssh())
