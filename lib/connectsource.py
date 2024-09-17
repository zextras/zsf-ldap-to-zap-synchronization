import json
from ldap3 import Server, Connection, ALL, set_config_parameter
from ldap3.utils.log import set_library_log_detail_level, OFF, BASIC
from ldap3.core.exceptions import LDAPException, LDAPBindError 

set_library_log_detail_level(OFF)
set_config_parameter('DEFAULT_CLIENT_ENCODING', 'utf-8')


class connect_ldap_client:

    def __init__(self, ldap_host, ldap_port, bind_dn, pwd, search_base='', ldap_filter='', attributsMapping='', realm='vide'):
        self.ldap_host = ldap_host
        self.ldap_port = ldap_port
        self.bind_dn = bind_dn
        self.pwd = pwd
        self.search_base = search_base
        self.ldap_filter = ldap_filter
        self.attributsMapping = attributsMapping
        self.domain = realm


    def flatten_list(self, _2d_list):
        flat_list = ''
        if type(_2d_list) is list and len(_2d_list) >= 1:
            if len(_2d_list) == 0:
                flat_list = ''
            elif len(_2d_list) == 1:
                flat_list = str(_2d_list[0])
            else:
                flat_list = []
                for element in _2d_list:
                    flat_list.append(element)
        return flat_list


    def cleanAliases(self, aliases):
        if len(aliases) == 1:
            aliasf = str(aliases).strip('[]')
        elif len(aliases) >= 2:
            aliasf = aliases
        else:
            aliasf = str(aliases).strip('[]')
        return aliasf


    def getLdap(self):
        LDAP = ''
        try:
            LDAP = Connection(
                Server(self.ldap_host, self.ldap_port, get_info=ALL),
                self.bind_dn,
                self.pwd,
                raise_exceptions=True,
                auto_bind=True)
        except LDAPBindError as e:
            logging.error(e)
            sys.exit(1)
        except LDAPException as e:
            logging.error(e)
            sys.exit(1)

        if not LDAP.bind():
            logging.error('error in bind' + str(LDAP.result))

        try:
            LDAP.search(self.search_base, self.ldap_filter, attributes=self.attributsMapping)
        except LDAPBindError as e:
            logging.error(e)
            sys.exit(1)

        except LDAPException as e:
            logging.error(e)
            sys.exit(1)

        records = {}
        dom_pattern = ('@' + str(self.domain))
        for count, entry in enumerate(LDAP.entries):
            accountSrc = {k: v for k, v in json.loads(entry.entry_to_json())["attributes"].items()}

            if 'mail' in accountSrc:  # and dom_pattern in accountSrc['mail']:
                accountName = accountSrc['mail'][0]
                accountdata = {accountName: {k: self.flatten_list([nv for nv in v]) for k, v in accountSrc.items()}}  # if k not in 'mail'}}
                records.update(accountdata)

        return records

