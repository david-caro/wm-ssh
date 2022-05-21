# wm-ssh

Ssh wrapper to expand wikimedia hostnames.

Currently it will try several sources, heavily using caches:
* Known working entries
* Known hosts file (https://config-master.wikimedia.org/known_hosts.ecdsa)
* Netbox (https://netbox.wikimedia.org)
* Openstack Browser (https://openstack-browser.toolforge.org)

# Installation
## pip

Just `pip install wm-ssh`, that should bring in a new binary, wm-ssh.

## Configuration
You can change the default settings by creating a configuration file, and passing the path using
`--config-file` or using the default `~/.config/wm-ssh/config.json`.

You can se an example of the loaded configuration running:
```
wm-ssh -v --print-config
```

### Known hosts url
This is a url with an ssh `known hosts` formatted file (see man for sshd(8) for the format), the
default one will use wikimedia bare metal hosts and non-cloud VMs.

### Openstack browser
Url to the openstack browser toolforge tool, with the list of all the VMs, the default will use
the current available one.


### Netbox
NOTE: The netbox feature needs you to have a token for netbox.wikimedia.org, see:
    https://netbox.wikimedia.org/user/api-tokens/

You can either configure the netbox cli and set just the path to the config file (the default is
`~/.config/netbox/config.json`), or you can set the netbox token and url directly  in the wm-ssh
config like (`~/.config/wm-ssh/config.json`):
```
{
    "netbox_config": {
        "netbox_url": "https://netbox.wikimedia.org/api",
        "api_token": "myapitokenwouldgohere"
    }
}
```

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

You can use the `utils/wm-ssh.complete` file (source it from your bashrc for example) to achieve bash completion features,
though they only work with wmcs openstack instances and known hosts.

For example, add in your `~/.bashrc` file:
```
source /path/to/git/repo/utirs/wm-ssh.complete
```

After that, it will autocomplete host names from the caches:
```
08:04 PM ~/Work/repos/per_user/david-caro/wm-ssh  (main|✚ 2)
dcaro@vulcanus$ wm-ssh an<tab><tab>

Display all 127 possibilities? (y or n)<y>

an-airflow1001.eqiad.wmnet                       an-presto1004.eqiad.wmnet                        an-worker1101.eqiad.wmnet
an-airflow1002.eqiad.wmnet                       an-presto1005.eqiad.wmnet                        an-worker1102.eqiad.wmnet
an-airflow1003.eqiad.wmnet                       an-test-client1001.eqiad.wmnet                   an-worker1103.eqiad.wmnet
analytics1058.eqiad.wmnet                        an-test-coord1001.eqiad.wmnet                    an-worker1104.eqiad.wmnet
analytics1059.eqiad.wmnet                        an-test-coord1002.eqiad.wmnet                    an-worker1105.eqiad.wmnet
analytics1060.eqiad.wmnet                        an-test-druid1001.eqiad.wmnet                    an-worker1106.eqiad.wmnet
analytics1061.eqiad.wmnet                        an-test-master1001.eqiad.wmnet                   an-worker1107.eqiad.wmnet
analytics1062.eqiad.wmnet                        an-test-master1002.eqiad.wmnet                   an-worker1108.eqiad.wmnet
analytics1063.eqiad.wmnet                        an-test-presto1001.eqiad.wmnet                   an-worker1109.eqiad.wmnet
analytics1064.eqiad.wmnet                        an-test-ui1001.eqiad.wmnet                       an-worker1110.eqiad.wmnet
analytics1065.eqiad.wmnet                        an-test-worker1001.eqiad.wmnet                   an-worker1111.eqiad.wmnet
analytics1066.eqiad.wmnet                        an-test-worker1002.eqiad.wmnet                   an-worker1112.eqiad.wmnet
analytics1067.eqiad.wmnet                        an-test-worker1003.eqiad.wmnet                   an-worker1113.eqiad.wmnet
analytics1068.eqiad.wmnet                        an-tool1005.eqiad.wmnet                          an-worker1114.eqiad.wmnet
analytics1069.eqiad.wmnet                        an-tool1007.eqiad.wmnet                          an-worker1115.eqiad.wmnet
analytics1070.eqiad.wmnet                        an-tool1008.eqiad.wmnet                          an-worker1116.eqiad.wmnet
analytics1071.eqiad.wmnet                        an-tool1009.eqiad.wmnet                          an-worker1117.eqiad.wmnet
analytics1072.eqiad.wmnet                        an-tool1010.eqiad.wmnet                          an-worker1118.eqiad.wmnet
analytics1073.eqiad.wmnet                        an-tool1011.eqiad.wmnet                          an-worker1119.eqiad.wmnet
analytics1074.eqiad.wmnet                        an-web1001.eqiad.wmnet                           an-worker1120.eqiad.wmnet
analytics1075.eqiad.wmnet                        an-worker1078.eqiad.wmnet                        an-worker1121.eqiad.wmnet
analytics1076.eqiad.wmnet                        an-worker1079.eqiad.wmnet                        an-worker1122.eqiad.wmnet
analytics1077.eqiad.wmnet                        an-worker1080.eqiad.wmnet                        an-worker1123.eqiad.wmnet
an-conf1001.eqiad.wmnet                          an-worker1081.eqiad.wmnet                        an-worker1124.eqiad.wmnet
an-conf1002.eqiad.wmnet                          an-worker1082.eqiad.wmnet                        an-worker1125.eqiad.wmnet
an-conf1003.eqiad.wmnet                          an-worker1083.eqiad.wmnet                        an-worker1126.eqiad.wmnet
an-coord1001.eqiad.wmnet                         an-worker1084.eqiad.wmnet                        an-worker1127.eqiad.wmnet
an-coord1002.eqiad.wmnet                         an-worker1085.eqiad.wmnet                        an-worker1128.eqiad.wmnet
an-db1001.eqiad.wmnet                            an-worker1086.eqiad.wmnet                        an-worker1129.eqiad.wmnet
an-db1002.eqiad.wmnet                            an-worker1087.eqiad.wmnet                        an-worker1130.eqiad.wmnet
an-db-backup-1.analytics.eqiad1.wikimedia.cloud  an-worker1088.eqiad.wmnet                        an-worker1131.eqiad.wmnet
andrewtest2.trove.eqiad1.wikimedia.cloud         an-worker1089.eqiad.wmnet                        an-worker1132.eqiad.wmnet
an-druid1001.eqiad.wmnet                         an-worker1090.eqiad.wmnet                        an-worker1133.eqiad.wmnet
an-druid1002.eqiad.wmnet                         an-worker1091.eqiad.wmnet                        an-worker1134.eqiad.wmnet
an-druid1003.eqiad.wmnet                         an-worker1092.eqiad.wmnet                        an-worker1135.eqiad.wmnet
an-druid1004.eqiad.wmnet                         an-worker1093.eqiad.wmnet                        an-worker1136.eqiad.wmnet
an-druid1005.eqiad.wmnet                         an-worker1094.eqiad.wmnet                        an-worker1137.eqiad.wmnet
an-launcher1002.eqiad.wmnet                      an-worker1095.eqiad.wmnet                        an-worker1138.eqiad.wmnet
an-master1001.eqiad.wmnet                        an-worker1096.eqiad.wmnet                        an-worker1139.eqiad.wmnet
an-master1002.eqiad.wmnet                        an-worker1097.eqiad.wmnet                        an-worker1140.eqiad.wmnet
an-presto1001.eqiad.wmnet                        an-worker1098.eqiad.wmnet                        an-worker1141.eqiad.wmnet
an-presto1002.eqiad.wmnet                        an-worker1099.eqiad.wmnet
an-presto1003.eqiad.wmnet                        an-worker1100.eqiad.wmnet

08:04 PM ~/Work/repos/per_user/david-caro/wm-ssh  (main|✚ 2)
dcaro@vulcanus$ wm-ssh an
```

