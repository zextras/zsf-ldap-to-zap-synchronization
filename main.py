#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=2 softtabstop=2

import argparse
import json
import logging
import os
import pathlib
import sys
import time

import zap_client


from lib.connectsource import connect_ldap_client


def get_zap_accounts(client: zap_client.Client) -> list[dict]:
    """
    Fetch the ZAP accounts.
    :param client: The ZAP client.
    :return: The list of ZAP accounts.
    """

    result = client.get_accounts()

    accounts = result['data']
    last_page = result['metadata']['last']

    for page in range(2, last_page + 1):
        accounts += client.get_accounts(page=page)['data']

    return accounts


def transform_ldap_accounts(ldap_accounts: list[dict], zap_accounts: dict[str, dict]):
    transformed_accounts = {}

    for name, attributes in ldap_accounts.items():
        transformed_accounts[name] = {}

        for attribute_k, attribute_v in attributes.items():
            if attribute_k in [
                'mail',
                'mailAlternateAddress',
                'zimbraMailAlias',
                'zimbraMailDeliveryAddress'
            ]:
                continue

            if attribute_v is None or isinstance(attribute_v, str) and len(attribute_v.strip()) <= 0:
                continue

            for mapping_k, mapping_v in config['attributesMapping'].items():
                if isinstance(mapping_v, (float, int, str)) and mapping_v == attribute_k:
                    transformed_accounts[name][mapping_k] = attribute_v

                if isinstance(mapping_v, dict):
                    for mapping_v_k, mapping_v_v in mapping_v.items():
                        if attribute_k == mapping_v_k:
                            for mapping_v_v_k, mapping_v_v_v in mapping_v_v.items():
                                if attribute_v == mapping_v_v_v:
                                    transformed_accounts[name].update({
                                        mapping_k: mapping_v_v_v
                                    })

        if name in zap_accounts and 'id' in zap_accounts[name]:
            transformed_accounts[name].update({'id': zap_accounts[name]['id']})

    return transformed_accounts


# Set log level.
logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())


# Parse arguments.
parser = argparse.ArgumentParser(
    prog=sys.argv[0],
    description='Synchronisation des comptes utilisateurs Carbonio',
    epilog='Zextras Service France'
)

parser.add_argument('-c', '--config', type=str, help='Configuration file')
parser.add_argument('-a', '--account', type=str, help='uniq account to get')
parser.add_argument('-n', '--noop', action="store_true", help='Dry run')

args = parser.parse_args()

# Read config file.
config_file_path = str(pathlib.Path(__file__).parent.resolve()) + '/' + str(
    args.config)

with open(config_file_path, 'rt') as config_file:
    config = json.load(config_file)

# Set destination and source attributes.
destination_attributes = [
    k for k, v in config['attributesMapping'].items()
    if v is not False and v != 'alias'
]

source_attributes = [
    (v[0] if isinstance(v, list) else v)
    for v in config['attributesMapping'].values()
    if isinstance(v, str) and v != 'alias' and v is not None and v != ""
]

# Create the LDAP client.
ldap_client = connect_ldap_client(
    config['ldap']['host'],
    config['ldap']['port'],
    config['ldap']['user'],
    config['ldap']['password'],
    config['ldap']['baseDN'],
    config['ldap']['filter'],
    source_attributes,
    config['domain']
)


# Get the LDAP accounts.
ldap_accounts = {
    name: attributes for name, attributes in ldap_client.getLdap().items()
    if name not in config['exclude']
}

# Create the ZAP client.
zap = zap_client.Client(
    api_key=zap_client.ApiKey(
        id=config['zap']['apiKey']['id'],
        secret=config['zap']['apiKey']['secret']
    ),
    host=config['zap']['host'],
    port=config['zap']['port'],
    secure=config['zap']['secure']
)

# Get the ZAP accounts.
zap_accounts = get_zap_accounts(zap)

# Filters out the ZAP accounts to exclude and transforms into a dict.
zap_accounts = {
    zap_account['name']: {'id': zap_account['id']} | {
        k: v for k, v in zap_account['attributes'].items()
        if k in destination_attributes
    }
    for zap_account in zap_accounts
    if zap_account['name'] not in config['exclude'] and
       zap_account['name'].split('@')[-1] == config['domain']
}


# Transform LDAP accounts.
transformed_ldap_accounts = transform_ldap_accounts(ldap_accounts, zap_accounts)


# Calculate the accounts to create, update and close.
accounts_to_create = {
    name: attributes for name, attributes in transformed_ldap_accounts.items()
    if name not in zap_accounts
}

accounts_to_update = {
    name: {'id': zap_accounts[name]['id']} | attributes
    for name, attributes in {
        name: {
            attribute_k: attribute_v
            for attribute_k, attribute_v in attributes.items()
            if attribute_k not in zap_accounts[name] or
               attribute_v != zap_accounts[name][attribute_k] and
               attribute_k != 'zimbraId' and
               (attribute_k == 'sn' or attribute_v)
        }
        for name, attributes in transformed_ldap_accounts.items()
        if name in zap_accounts and
           zap_accounts[name]['zimbraAccountStatus'] != 'closed'
    }.items() if len(attributes) > 0
}

accounts_to_close = {
    name: {'id': attributes['id']} for name, attributes in zap_accounts.items()
    if name not in transformed_ldap_accounts and
       attributes['zimbraAccountStatus'] != 'closed'
}

logging.info(f'{len(accounts_to_create)} accounts to create')
logging.info(f'{len(accounts_to_update)} accounts to update')
logging.info(f'{len(accounts_to_close)} accounts to close')


# Create the accounts to create.
if config['actions']['create']:
    for name, attributes in accounts_to_create.items():
        logging.info(f'Creating account {name} with attributes: {attributes}')

        if not args.noop:
            created_account = zap.create_account({'name': name} | attributes)

            time.sleep(2)

            for distribution_list_id in config['addNewAccountsToDistributionLists']:
                logging.info(f'Adding account {name} to distribution list {distribution_list_id}')

                zap.update_distribution_list(distribution_list_id, {
                    'membersToAdd': [name]
                })

                time.sleep(2)


# Update the accounts to update.
if config['actions']['update']:
    for name, attributes in accounts_to_update.items():
        payload = {
            k: v for k, v in attributes.items() if k != 'id'
        }

        logging.info(f'Updating account {name} with attributes: {payload}')

        if not args.noop:
            zap.update_account(attributes['id'], payload)

            time.sleep(2)


# Close the accounts to close.
if config['actions']['close']:
    for name, attributes in accounts_to_close.items():
        logging.info(f'Closing account {name}.')

        if not args.noop:
            zap.update_account(attributes['id'], {
                'zimbraAccountStatus': 'closed'
            })

            time.sleep(2)
