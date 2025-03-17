#!/bin/bash

# Install the Python ZAP client in a venv:
# https://github.com/zextras/zsf-zap-client

python -m venv .venv

source .venv/bin/activate

pip install ldap3

wget https://github.com/zextras/zsf-zap-client/releases/download/python-v0.1.0/zap_client-0.1.0-py3-none-any.whl

pip install zap_client-0.1.0-py3-none-any.whl
