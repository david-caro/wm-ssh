from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from wm_ssh import cli


def get_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = {
        "netbox_url": None,
        "api_token": None,
    }
    if overrides:
        config.update(overrides)

    return config


def test_NetboxResolver_get_host_tries_phys_host_only_if_found():
    netbox_resolver = cli.NetboxResolver(api_token="dummytoken", netbox_url="dummy_url", cachefile=None)
    netbox_resolver.get_physical = MagicMock(spec=netbox_resolver.get_physical)
    netbox_resolver.get_physical.return_value = "test.host.found"
    netbox_resolver.get_vm = MagicMock(spec=netbox_resolver.get_vm)
    result = netbox_resolver.get_host(hostname="test")
    assert result == "test.host.found"
    netbox_resolver.get_physical.assert_called_once()
    netbox_resolver.get_vm.assert_not_called()
