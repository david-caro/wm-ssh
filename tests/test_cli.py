from typing import Any, Dict, Optional
from unittest.mock import patch

from wm_ssh import cli


def get_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = {
        "netbox_url": None,
        "api_token": None,
    }
    if overrides:
        config.update(overrides)

    return config


@patch("wm_ssh.cli.get_vm")
@patch("wm_ssh.cli.get_physical")
def test_get_host_from_netbox_tries_phys_host_only_if_found(get_physical_mock, get_vm_mock):
    get_physical_mock.return_value = "test.host.found"
    result = cli.get_host_from_netbox(config=get_config(), hostname="test", cachefile=None)

    assert result == "test.host.found"
    get_physical_mock.assert_called_once()
    get_vm_mock.assert_not_called()
