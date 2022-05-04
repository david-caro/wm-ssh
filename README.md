# wm-ssh

Ssh wrapper to expand wikimedia hostnames.

Currently it will try several sources, heavily using caches:
* Known working entries
* Netbox (https://netbox.wikimedia.org)
* Openstack Browser (https://openstack-browser.toolforge.org)

NOTE: The netbox feature needs you to have a token for netbox.wikimedia.org, see:
    https://netbox.wikimedia.org/user/api-tokens/


# Installation
## pip

Just `pip install wm-ssh`, that should bring in a new binary, wm-ssh.

## Running from code

Note that this mode will require some tweaks in the auto-completing for it to work.

Clone the code:
```
git clone git@github.com:david-caro/wm-ssh.git
```

Install dependencies with poetry:
```
poetry install
```

Run with poetry:
```
poetry run wm-ssh <MYHOST>
```


# Bash completion

You can use the wm-ssh.complete file (source it from your bashrc for example) to achieve bash completion features,
though they only work with wmcs openstack instances and known hosts.

