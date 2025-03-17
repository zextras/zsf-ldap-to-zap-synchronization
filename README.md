# Installation

The preferred installation method is the `install.sh` script.
It creates a virtual environment and installs
the `zap_client` dependency from a GitHub release.

## Manual installation

If you want to install the dependency manually, clone the ZAP client repository
(https://github.com/zextras/zsf-zap-client) and copy the module folder
(`python/zap-client/zap_client` into the root of this project).

Also, install the `ldap3` Python package:

```shell
pipi install ldap3
```

# Usage

If you have installed the dependency through the installation script,
remember to load the virtual environment where it is installed
(`source .venv/bin/activate`).

Fill in the config file (`config.json`)
and run the synchronization script with it:

```shell
python main.py --config config.json
```
