"""
Test suite for Intersite application
"""
import unittest
from acitoolkit import (AppProfile, EPG, Endpoint, Interface, L2Interface, Context, BridgeDomain, Session, Tenant,
                        IPEndpoint, OutsideL3, OutsideEPG, OutsideNetwork, Contract)
from intersite import execute_tool, IntersiteTag
import logging
from StringIO import StringIO
import mock
import sys

if sys.version_info.major == 2:
    import __builtin__ as builtins
else:
    import builtins
import json
import time
from requests import ConnectionError

try:
    from multisite_test_credentials import (SITE1_IPADDR, SITE1_LOGIN, SITE1_PASSWORD, SITE1_URL,
                                            SITE2_IPADDR, SITE2_LOGIN, SITE2_PASSWORD, SITE2_URL)
except ImportError:
    print '''
            Please create a file called multisite_test_credentials.py with the following:

            SITE1_IPADDR = ''
            SITE1_LOGIN = ''
            SITE1_PASSWORD = ''
            SITE1_URL = 'http://' + SITE1_IPADDR  # change http to https for SSL

            SITE2_IPADDR = ''
            SITE2_LOGIN = ''
            SITE2_PASSWORD = ''
            SITE2_URL = 'http://' + SITE2_IPADDR
            '''
    sys.exit(0)


class FakeStdio(object):
    """
    FakeStdio : Class to fake writing to stdio and store it so that it can be verified
    """
    def __init__(self):
        self.output = []

    def write(self, *args, **kwargs):
        """
        Mock the write routine

        :param args: Args passed to stdio write
        :param kwargs: Kwargs passed to stdio write
        :return: None
        """
        for arg in args:
            self.output.append(arg)

    def verify_output(self, output):
        """
        Verify that the output is the same as generated previously

        :param output: Output to test for
        :return: True if the same as the stored output. False otherwise
        """
        return output == self.output


class TestToolOptions(unittest.TestCase):
    """
    Test cases for testing the command line arguments
    """
    @staticmethod
    def get_logging_level():
        """
        Return the current logger level

        :return: Logger level
        """
        return logging.getLevelName(logging.getLogger().getEffectiveLevel())

    def test_no_options(self):
        """
        Test no configuration file given.  Verify that it generates an error message
        """
        args = mock.Mock()
        args.debug = None
        args.generateconfig = None
        args.config = None
        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            execute_tool(args)
            self.assertEqual(fake_out.getvalue(), '%% No configuration file given.\n')

    def test_generateconfig(self):
        """
        Test generate sample configuration file.  Verify that it generates the correct text message
        """
        args = mock.Mock()
        args.debug = None
        args.generateconfig = True
        args.config = None
        expected_text = ('Sample configuration file written to sample_config.json\n'
                         "Replicate the site JSON for each site.\n"
                         "    Valid values for use_https and local are 'True' and 'False'\n"
                         "    One site must have local set to 'True'\n"
                         'Replicate the export JSON for each exported contract.\n')
        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            execute_tool(args)
            self.assertEqual(fake_out.getvalue(), expected_text)

    def test_config_bad_filename(self):
        """
        Test no configuration file given.  Verify that it generates an error message
        """
        args = mock.Mock()
        args.debug = None
        args.generateconfig = None
        args.config = 'jkdhfdskjfhdsfkjhdsfdskjhf.jdkhfkfjh'
        expected_text = '%% Unable to open configuration file jkdhfdskjfhdsfkjhdsfdskjhf.jdkhfkfjh\n'
        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            execute_tool(args)
            self.assertEqual(fake_out.getvalue(), expected_text)


class TestBadConfiguration(unittest.TestCase):
    """
    Test various invalid configuration files
    """
    @staticmethod
    def create_empty_config_file():
        """
        Generate an empty configuration file with only a single empty Site policy
        :return: dictionary containing the configuration
        """
        config = {
            "config": [
                {
                    "site": {
                        "username": "",
                        "name": "",
                        "ip_address": "",
                        "password": "",
                        "local": "",
                        "use_https": ""
                    }
                }
            ]
        }
        return config

    @staticmethod
    def get_args():
        """
        Generate an empty command line arguments
        :return: Instance of Mock to represent the command line arguments
        """
        args = mock.Mock()
        args.debug = None
        args.generateconfig = None
        args.config = 'doesntmatter'
        return args

    def test_no_config_keyword(self):
        """
        Test no "config" present in the JSON.  Verify that the correct error message is generated.
        :return: None
        """
        args = self.get_args()
        config = {
            "site": {
                "username": "",
                "name": "",
                "ip_address": "",
                "password": "",
                "local": "",
                "use_https": ""
            }
        }
        temp = sys.stdout
        fake_out = FakeStdio()
        sys.stdout = fake_out

        config_filename = 'testsuite_cfg.json'
        args.config = config_filename
        config_file = open(config_filename, 'w')
        config_file.write(str(json.dumps(config)))
        config_file.close()

        execute_tool(args, test_mode=True)
        sys.stdout = temp
        self.assertTrue(fake_out.verify_output(['%% Invalid configuration file', '\n']))

    def test_site_with_bad_ipaddress(self):
        """
        Test invalid IP address value in the JSON.  Verify that the correct exception is generated.
        :return: None
        """
        args = self.get_args()
        config = self.create_empty_config_file()
        config['config'][0]['site']['ip_address'] = 'bogu$'

        config_filename = 'testsuite_cfg.json'
        args.config = config_filename
        config_file = open(config_filename, 'w')
        config_file.write(str(json.dumps(config)))
        config_file.close()

        self.assertRaises(ValueError, execute_tool, args, test_mode=True)

    def test_site_with_good_ipaddress_and_bad_userid(self):
        """
        Test good IP address value but invalid username in the JSON.  Verify that the correct exception is generated.
        :return: None
        """
        args = self.get_args()
        config = self.create_empty_config_file()
        config['config'][0]['site']['username'] = ''
        config['config'][0]['site']['ip_address'] = '172.31.216.100'
        config['config'][0]['site']['local'] = 'True'
        config['config'][0]['site']['use_https'] = 'True'

        config_filename = 'testsuite_cfg.json'
        args.config = config_filename
        config_file = open(config_filename, 'w')
        config_file.write(str(json.dumps(config)))
        config_file.close()

        self.assertRaises(ValueError, execute_tool, args, test_mode=True)


class BaseTestCase(unittest.TestCase):
    """
    BaseTestCase: Base class to be used for creating other TestCases. Not to be instantiated directly.
    """
    def setup_remote_site(self):
        """
        Set up the remote site. Meant to be overridden by inheriting classes
        """
        raise NotImplementedError

    def setup_local_site(self):
        """
        Set up the local site. Meant to be overridden by inheriting classes
        """
        raise NotImplementedError

    def setUp(self):
        """
        Set up the test case.  Setup the remote and local site.
        :return: None
        """
        self.setup_remote_site()
        self.setup_local_site()

    def tearDown(self):
        """
        Tear down the test case.  Tear down the remote and local site.
        :return: None
        """
        self.teardown_local_site()
        self.teardown_remote_site()
        time.sleep(2)

    @staticmethod
    def create_site_config():
        """
        Generate a basic configuration containing the local and remote site policies.
        Actual site credentials are set in global variables imported from multisite_test_credentials
        :return: dictionary containing the configuration
        """
        config = {
            "config": [
                {
                    "site": {
                        "username": "%s" % SITE1_LOGIN,
                        "name": "Site1",
                        "ip_address": "%s" % SITE1_IPADDR,
                        "password": "%s" % SITE1_PASSWORD,
                        "local": "True",
                        "use_https": "False"
                    }
                },
                {
                    "site": {
                        "username": "%s" % SITE2_LOGIN,
                        "name": "Site2",
                        "ip_address": "%s" % SITE2_IPADDR,
                        "password": "%s" % SITE2_PASSWORD,
                        "local": "False",
                        "use_https": "False"
                    }
                }
            ]
        }
        return config

    @staticmethod
    def write_config_file(config, args):
        """
        Write the configuration as a temporary file and set the command line arguments to read the file
        :param config: dictionary containing the configuration
        :param args: Mock of the command line arguments
        :return: None
        """
        config_filename = 'testsuite_cfg.json'
        args.config = config_filename
        config_file = open(config_filename, 'w')
        config_file.write(str(json.dumps(config)))
        config_file.close()

    def verify_remote_site_has_entry(self, mac, ip, tenant_name, l3out_name, remote_epg_name):
        """
        Verify that the remote site has the entry
        :param mac: String containing the MAC address of the endpoint to find on the remote site
        :param ip: String containing the IP address of the endpoint to find on the remote site
        :param tenant_name: String containing the remote tenant name holding the endpoint
        :param l3out_name: String containing the remote OutsideL3 name holding the endpoint
        :param remote_epg_name: String containing the remote OutsideEPG on the remote OutsideL3 holding the endpoint
        :return: True if the remote site has the endpoint. False otherwise
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        query = ('/api/mo/uni/tn-%s/out-%s/instP-%s.json?query-target=children' % (tenant_name, l3out_name, remote_epg_name))
        resp = site2.get(query)
        self.assertTrue(resp.ok)

        found = False
        for item in resp.json()['imdata']:
            if 'l3extSubnet' in item:
                if item['l3extSubnet']['attributes']['ip'] == ip + '/32':
                    found = True
                    break
        if not found:
            return False
        return True

    def verify_remote_site_has_entry_with_provided_contract(self, mac, ip, tenant_name, l3out_name, remote_epg_name, contract_name):
        """
        Verify that the remote site has the entry and provides the specfied contract
        :param mac: String containing the MAC address of the endpoint to find on the remote site
        :param ip: String containing the IP address of the endpoint to find on the remote site
        :param tenant_name: String containing the remote tenant name holding the endpoint
        :param l3out_name: String containing the remote OutsideL3 name holding the endpoint
        :param remote_epg_name: String containing the remote OutsideEPG on the remote OutsideL3 holding the endpoint
        :param contract_name: String containing the contract name that the remote OutsideEPG should be providing
        :return: True if the remote site has the endpoint. False otherwise
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        query = '/api/mo/uni/tn-%s/out-%s.json?query-target=subtree' % (tenant_name, l3out_name)
        resp = site2.get(query)
        self.assertTrue(resp.ok)

        # Look for l3extInstP
        found = False
        for item in resp.json()['imdata']:
            if 'l3extInstP' in item:
                if item['l3extInstP']['attributes']['name'] == remote_epg_name:
                    found = True
                    break
        if not found:
            return False

        # Verify that the l3extInstP is providing the contract
        found = False
        for item in resp.json()['imdata']:
            if 'fvRsProv' in item:
                if item['fvRsProv']['attributes']['tnVzBrCPName'] == contract_name:
                    found = True
                    break
        if not found:
            return False

        return self.verify_remote_site_has_entry(mac, ip, tenant_name, l3out_name, remote_epg_name)

    def verify_remote_site_has_policy(self, tenant_name, l3out_name, instp_name):
        """
        Verify that the remote site has the policy
        :param tenant_name: String containing the remote tenant name holding the policy
        :param l3out_name: String containing the remote OutsideL3 name holding the policy
        :param instp_name: String containing the remote OutsideEPG holding the policy
        :return: True if the remote site has the policy. False otherwise
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        query = ('/api/mo/uni/tn-%s/out-%s/instP-%s.json' % (tenant_name, l3out_name, instp_name))
        resp = site2.get(query)
        self.assertTrue(resp.ok)

        found = False
        for item in resp.json()['imdata']:
            if 'l3extInstP' in item:
                found = True
                break
        if not found:
            return False
        return True

    def teardown_local_site(self):
        """
        Teardown the local site configuration
        """
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        if not resp.ok:
            print resp, resp.text
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        tenant.mark_as_deleted()

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def teardown_remote_site(self):
        """
        Teardown the remote site configuration
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        tenant.mark_as_deleted()

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)
        time.sleep(2)

    @staticmethod
    def get_args():
        """
        Get a mock of the command line arguments
        :return: Mock instance representing the command line arguments
        """
        args = mock.Mock()
        args.debug = None
        args.generateconfig = None
        args.config = 'doesntmatter'
        return args

    def remove_endpoint(self, mac, ip, tenant_name, app_name, epg_name):
        """
        Remove the endpoint
        :param mac: String containing the MAC address of the endpoint
        :param ip: String containing the IP address of the endpoint
        :param tenant_name: String containing the tenant name of the endpoint
        :param app_name: String containing the AppProfile name holding the endpoint
        :param epg_name: String containing the EPG name holding the endpoint
        :return: None
        """
        self.add_endpoint(mac, ip, tenant_name, app_name, epg_name, mark_as_deleted=True)

    def add_endpoint(self, mac, ip, tenant_name, app_name, epg_name, mark_as_deleted=False):
        """
        Add the endpoint
        :param mac: String containing the MAC address of the endpoint
        :param ip: String containing the IP address of the endpoint
        :param tenant_name: String containing the tenant name of the endpoint
        :param app_name: String containing the AppProfile name holding the endpoint
        :param epg_name: String containing the EPG name holding the endpoint
        :param mark_as_deleted: True or False. True if the endpoint is to be marked as deleted. Default is False
        :return: None
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant(tenant_name)
        app = AppProfile(app_name, tenant)
        epg = EPG(epg_name, app)

        ep = Endpoint(mac, epg)
        ep.mac = mac
        ep.ip = ip
        if mark_as_deleted:
            ep.mark_as_deleted()
        l3ep = IPEndpoint(ip, ep)

        # Create the physical interface object
        intf = Interface('eth', '1', '101', '1', '38')
        vlan_intf = L2Interface('vlan-5', 'vlan', '5')
        vlan_intf.attach(intf)

        # Attach the EPG to the VLAN interface
        epg.attach(vlan_intf)

        # Assign it to the L2Interface
        ep.attach(vlan_intf)

        urls = intf.get_url()
        jsons = intf.get_json()

        # Set the the phys domain, infra, and fabric
        for k in range(0, len(urls)):
            if jsons[k] is not None:
                resp = site1.push_to_apic(urls[k], jsons[k])
                self.assertTrue(resp.ok)

        # Push the endpoint
        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)


class BaseEndpointTestCase(BaseTestCase):
    """
    Base class for the endpoint test cases
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        app = AppProfile('app', tenant)
        epg = EPG('epg', app)

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out = OutsideL3('l3out', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def create_config_file(self):
        """
        Create the configuration
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export":
                {
                    "tenant": "intersite-testsuite",
                    "app": "app",
                    "epg": "epg",
                    "remote_epg": "intersite-testsuite-app-epg",
                    "remote_sites":
                        [
                            {
                                "site":
                                    {
                                        "name": "Site2",
                                        "interfaces":
                                            [
                                                {
                                                    "l3out":
                                                        {
                                                            "name": "l3out",
                                                            "tenant": "intersite-testsuite"
                                                        }
                                                }
                                            ]
                                    }
                            }
                        ]
                }
        }
        config['config'].append(export_policy)
        return config

    def setup_with_endpoint(self):
        """
        Set up the configuration with an endpoint
        :return: 2 strings containing the MAC and IP address of the endpoint
        """
        args = self.get_args()
        self.write_config_file(self.create_config_file(), args)

        execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        return mac, ip


class TestBasicEndpoints(BaseEndpointTestCase):
    """
    Basic tests for endpoints
    """
    def test_basic_add_endpoint(self):
        """
        Test add endpoint
        """
        mac, ip = self.setup_with_endpoint()
        time.sleep(2)
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

    def test_basic_add_multiple_endpoint(self):
        """
        Test add multiple endpoints
        """
        mac1, ip1 = self.setup_with_endpoint()
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

    def test_basic_remove_endpoint(self):
        """
        Test remove endpoint
        """
        mac, ip = self.setup_with_endpoint()
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.remove_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

    def test_basic_remove_one_of_multiple_endpoint(self):
        """
        Test remove one of multiple endpoints
        """
        mac1, ip1 = self.setup_with_endpoint()
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

        self.remove_endpoint(mac1, ip1, 'intersite-testsuite', 'app', 'epg')
        self.assertFalse(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))


class TestMultipleEPG(BaseTestCase):
    """
    Test multiple EPGs
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        app1 = AppProfile('app1', tenant)
        epg1 = EPG('epg1', app1)
        app2 = AppProfile('app2', tenant)
        epg2 = EPG('epg2', app2)

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out = OutsideL3('l3out', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def create_config_file(self):
        """
        Create the configuration
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app1",
                "epg": "epg1",
                "remote_epg": "intersite-testsuite-app1-epg1",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app2",
                "epg": "epg2",
                "remote_epg": "intersite-testsuite-app2-epg2",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def test_basic_add_endpoint(self):
        """
        Test add endpoint
        """
        args = self.get_args()
        config = self.create_config_file()

        config_filename = 'testsuite_cfg.json'
        args.config = config_filename
        config_file = open(config_filename, 'w')
        config_file.write(str(json.dumps(config)))
        config_file.close()

        execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app1-epg1'))

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app1', 'epg1')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app1-epg1'))

    def test_basic_add_multiple_endpoint(self):
        """
        Test adding multiple endpoints
        """
        args = self.get_args()
        config = self.create_config_file()

        config_filename = 'testsuite_cfg.json'
        args.config = config_filename
        config_file = open(config_filename, 'w')
        config_file.write(str(json.dumps(config)))
        config_file.close()

        execute_tool(args, test_mode=True)

        time.sleep(2)
        mac1 = '00:11:22:33:33:34'
        ip1 = '3.4.3.5'
        self.add_endpoint(mac1, ip1, 'intersite-testsuite', 'app1', 'epg1')
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app2', 'epg2')
        mac3 = '00:11:22:33:33:36'
        ip3 = '3.4.3.7'
        self.add_endpoint(mac3, ip3, 'intersite-testsuite', 'app2', 'epg2')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app1-epg1'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app2-epg2'))
        self.assertTrue(self.verify_remote_site_has_entry(mac3, ip3, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app2-epg2'))

    def test_basic_remove_endpoint(self):
        """
        Test remove the endpoint
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        time.sleep(2)
        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app1', 'epg1')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app1-epg1'))
        self.remove_endpoint(mac, ip, 'intersite-testsuite', 'app1', 'epg1')
        time.sleep(2)
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app1-epg1'))

    def test_basic_remove_one_of_multiple_endpoint(self):
        """
        Test remove one of multiple endpoints
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        time.sleep(2)
        mac1 = '00:11:22:33:33:34'
        ip1 = '3.4.3.5'
        self.add_endpoint(mac1, ip1, 'intersite-testsuite', 'app1', 'epg1')
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app2', 'epg2')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app1-epg1'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app2-epg2'))

        self.remove_endpoint(mac1, ip1, 'intersite-testsuite', 'app1', 'epg1')
        self.assertFalse(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out',
                                                           'intersite-testsuite-app1-epg1'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app2-epg2'))


class TestBasicExistingEndpoints(BaseTestCase):
    """
    Tests for endpoints already existing
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        app = AppProfile('app', tenant)
        epg = EPG('epg', app)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out = OutsideL3('l3out', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def create_config_file(self):
        """
        Create the configuration
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def test_basic_add_endpoint(self):
        """
        Test add the endpoint
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)
        time.sleep(2)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

    def test_basic_remove_endpoint(self):
        """
        Test remove the endpoint
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        time.sleep(2)
        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'

        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.remove_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))


class TestBasicExistingEndpointsAddPolicyLater(BaseTestCase):
    """
    Tests for previously existing endpoints and policy is added later
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        app = AppProfile('app', tenant)
        epg = EPG('epg', app)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out = OutsideL3('l3out', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def create_config_file(self):
        """
        Create the configuration
        :return: Dictionary containing the configuration
        """
        return self.create_site_config()

    @staticmethod
    def create_export_policy():
        """
        Create the export policy
        :return: Dictionary containing the configuration
        """
        config = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        return config

    def test_basic_add_endpoint(self):
        """
        Test adding the endpoint
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        collector = execute_tool(args, test_mode=True)
        time.sleep(2)

        config['config'].append(self.create_export_policy())
        self.write_config_file(config, args)
        collector.reload_config()
        time.sleep(2)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

    def test_basic_remove_endpoint(self):
        """
        Test removing the endpoint
        """
        args = self.get_args()
        config = self.create_config_file()
        config['config'].append(self.create_export_policy())
        self.write_config_file(config, args)

        collector = execute_tool(args, test_mode=True)

        time.sleep(2)
        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

        config = self.create_config_file()
        self.write_config_file(config, args)
        collector.reload_config()
        time.sleep(2)
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))


class TestExportPolicyRemoval(BaseTestCase):
    """
    Tests for export policy removal
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        tenant.mark_as_deleted()
        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)
        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

        time.sleep(2)

        tenant = Tenant('intersite-testsuite')
        app = AppProfile('app', tenant)
        epg1 = EPG('epg', app)
        epg2 = EPG('epg2', app)
        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)
        time.sleep(2)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out = OutsideL3('l3out', tenant)
        l3out2 = OutsideL3('l3out2', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def create_diff_epg_config_file(self):
        """
        Create a configuration with different EPGs
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg2",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def create_config_file(self):
        """
        Create the configuration
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg2",
                "remote_epg": "intersite-testsuite-app-epg2",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out2",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def test_basic_remove_policy(self):
        """
        Test removing the policy
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        collector = execute_tool(args, test_mode=True)
        time.sleep(4)
        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg2'))

        config = self.create_site_config()
        self.write_config_file(config, args)
        collector.reload_config()

        time.sleep(4)
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertFalse(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertFalse(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg2'))

    def test_basic_change_policy_name(self):
        """
        Test changing the policy name
        """
        args = self.get_args()
        config = self.create_config_file()
        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.write_config_file(config, args)
        collector = execute_tool(args, test_mode=True)
        time.sleep(4)
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

        config = self.create_diff_epg_config_file()
        self.write_config_file(config, args)
        collector.reload_config()

        time.sleep(4)

        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertFalse(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg2'))
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg2'))


class TestBasicEndpointsWithContract(BaseTestCase):
    """
    Basic Tests for endpoints with a contract
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        app = AppProfile('app', tenant)
        epg = EPG('epg', app)

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out = OutsideL3('l3out', tenant)

        contract = Contract('contract-1', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def create_config_file(self):
        """
        Create the configuration
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite",
                                        "provides": [
                                            {
                                                "contract_name": "contract-1"
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def test_basic_add_endpoint(self):
        """
        Test adding endpoint
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry_with_provided_contract(mac, ip, 'intersite-testsuite', 'l3out',
                                                                                  'intersite-testsuite-app-epg', 'contract-1'))

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry_with_provided_contract(mac, ip, 'intersite-testsuite', 'l3out',
                                                                                 'intersite-testsuite-app-epg', 'contract-1'))

    def test_basic_add_multiple_endpoint(self):
        """
        Test adding multiple endpoints
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        time.sleep(2)
        mac1 = '00:11:22:33:33:34'
        ip1 = '3.4.3.5'
        self.add_endpoint(mac1, ip1, 'intersite-testsuite', 'app', 'epg')
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry_with_provided_contract(mac1, ip1, 'intersite-testsuite', 'l3out',
                                                                                 'intersite-testsuite-app-epg', 'contract-1'))
        self.assertTrue(self.verify_remote_site_has_entry_with_provided_contract(mac2, ip2, 'intersite-testsuite', 'l3out',
                                                                                 'intersite-testsuite-app-epg', 'contract-1'))

    def test_basic_remove_endpoint(self):
        """
        Test removing endpoint
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        time.sleep(2)
        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry_with_provided_contract(mac, ip, 'intersite-testsuite', 'l3out',
                                                                                 'intersite-testsuite-app-epg', 'contract-1'))
        self.remove_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        self.assertFalse(self.verify_remote_site_has_entry_with_provided_contract(mac, ip, 'intersite-testsuite', 'l3out',
                                                                                  'intersite-testsuite-app-epg', 'contract-1'))

    def test_basic_remove_one_of_multiple_endpoint(self):
        """
        Test removing one of multiple endpoints
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        time.sleep(2)
        mac1 = '00:11:22:33:33:34'
        ip1 = '3.4.3.5'
        self.add_endpoint(mac1, ip1, 'intersite-testsuite', 'app', 'epg')
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry_with_provided_contract(mac1, ip1, 'intersite-testsuite', 'l3out',
                                                                                 'intersite-testsuite-app-epg', 'contract-1'))
        self.assertTrue(self.verify_remote_site_has_entry_with_provided_contract(mac2, ip2, 'intersite-testsuite', 'l3out',
                                                                                 'intersite-testsuite-app-epg', 'contract-1'))

        self.remove_endpoint(mac1, ip1, 'intersite-testsuite', 'app', 'epg')
        self.assertFalse(self.verify_remote_site_has_entry_with_provided_contract(mac1, ip1, 'intersite-testsuite', 'l3out',
                                                                                  'intersite-testsuite-app-epg', 'contract-1'))
        self.assertTrue(self.verify_remote_site_has_entry_with_provided_contract(mac2, ip2, 'intersite-testsuite', 'l3out',
                                                                                 'intersite-testsuite-app-epg', 'contract-1'))


class TestBasicEndpointMove(BaseTestCase):
    """
    Tests for an endpoint that moves
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        context = Context('vrf', tenant)
        bd = BridgeDomain('bd', tenant)
        app = AppProfile('app', tenant)
        epg = EPG('epg1', app)
        epg2 = EPG('epg2', app)
        bd.add_context(context)
        epg.add_bd(bd)
        epg2.add_bd(bd)

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out = OutsideL3('l3out', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def create_config_file(self):
        """
        Create the configuration
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg1",
                "remote_epg": "intersite-testsuite-app-epg1",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg2",
                "remote_epg": "intersite-testsuite-app-epg2",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def setup_with_endpoint(self):
        """
        Set up the local site with the endpoint
        :return: 2 strings containing the MAC and IP address of the endpoint
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg1'))

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg1')
        return mac, ip

    def test_basic_add_endpoint(self):
        """
        Test add endpoint
        """
        mac, ip = self.setup_with_endpoint()
        time.sleep(2)
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg1'))

    def test_basic_add_multiple_endpoint(self):
        """
        Test add multiple endpoints
        """
        mac1, ip1 = self.setup_with_endpoint()
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app', 'epg2')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app-epg1'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app-epg2'))

    def test_basic_remove_endpoint(self):
        """
        Test removing the endpoint
        """
        mac, ip = self.setup_with_endpoint()
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app-epg1'))
        self.remove_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg1')
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out',
                                                           'intersite-testsuite-app-epg1'))

    def test_basic_remove_one_of_multiple_endpoint(self):
        """
        Test removing one of multiple endpoints
        """
        mac1, ip1 = self.setup_with_endpoint()
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app', 'epg1')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app-epg1'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app-epg1'))

        self.remove_endpoint(mac1, ip1, 'intersite-testsuite', 'app', 'epg1')
        self.assertFalse(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out',
                                                           'intersite-testsuite-app-epg1'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out',
                                                          'intersite-testsuite-app-epg1'))


class TestPolicyChangeProvidedContract(BaseTestCase):
    """
    Tests to cover changing the provided contract within the policy
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        app = AppProfile('app', tenant)
        epg = EPG('epg', app)

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out = OutsideL3('l3out', tenant)

        contract = Contract('contract-1', tenant)
        contract = Contract('contract-2', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def create_config_file_before(self):
        """
        Create the configuration before changing the provided contract
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite",
                                        "provides": [
                                            {
                                                "contract_name": "contract-1",
                                            },
                                            {
                                                "contract_name": "contract-2",
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def create_config_file_after(self):
        """
        Create the configuration after changing the provided contract
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite",
                                        "provides": [
                                            {
                                                "contract_name": "contract-1"
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def verify_remote_site_has_entry_before(self, mac, ip):
        """
        Verify that the remote site has the entry before changing the policy
        :param mac: String containing the endpoint MAC address
        :param ip: String containing the endpoint IP address
        :return: True or False.  True if the remote site has the entry
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        query = ('/api/mo/uni/tn-intersite-testsuite/out-l3out.json?query-target=subtree')
        resp = site2.get(query)
        self.assertTrue(resp.ok)

        # Look for l3extInstP
        found = False
        for item in resp.json()['imdata']:
            if 'l3extInstP' in item:
                if item['l3extInstP']['attributes']['name'] == 'intersite-testsuite-app-epg':
                    found = True
                    break
        if not found:
            return False

        # Verify that the l3extInstP is providing the contracts
        found_contract1 = False
        found_contract2 = False
        for item in resp.json()['imdata']:
            if 'fvRsProv' in item:
                if item['fvRsProv']['attributes']['tnVzBrCPName'] == 'contract-1':
                    found_contract1 = True
                if item['fvRsProv']['attributes']['tnVzBrCPName'] == 'contract-2':
                    found_contract2 = True
        if not found_contract1 or not found_contract2:
            return False

        # Look for l3extSubnet
        query = '/api/mo/uni/tn-intersite-testsuite/out-l3out/instP-intersite-testsuite-app-epg.json?query-target=subtree'
        resp = site2.get(query)
        self.assertTrue(resp.ok)

        # Look for l3extSubnet
        found = False
        for item in resp.json()['imdata']:
            if 'l3extSubnet' in item:
                if item['l3extSubnet']['attributes']['name'] == ip:
                    found = True
                    break
        if not found:
            return False
        return True

    def verify_remote_site_has_entry_after(self, mac, ip):
        """
        Verify that the remote site has the entry after changing the policy
        :param mac: String containing the endpoint MAC address
        :param ip: String containing the endpoint IP address
        :return: True or False.  True if the remote site has the entry
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        query = ('/api/mo/uni/tn-intersite-testsuite/out-l3out.json?query-target=subtree')
        resp = site2.get(query)
        self.assertTrue(resp.ok)

        # Look for l3extInstP
        found = False
        for item in resp.json()['imdata']:
            if 'l3extInstP' in item:
                if item['l3extInstP']['attributes']['name'] == 'intersite-testsuite-app-epg':
                    found = True
                    break
        if not found:
            return False

        # Verify that the l3extInstP is providing the contract
        found_contract1 = False
        found_contract2 = False
        for item in resp.json()['imdata']:
            if 'fvRsProv' in item:
                if item['fvRsProv']['attributes']['tnVzBrCPName'] == 'contract-1':
                    found_contract1 = True
                if item['fvRsProv']['attributes']['tnVzBrCPName'] == 'contract-2':
                    found_contract2 = True
        if not found_contract1 or found_contract2:
            return False

        # Look for l3extSubnet
        query = '/api/mo/uni/tn-intersite-testsuite/out-l3out/instP-intersite-testsuite-app-epg.json?query-target=subtree'
        resp = site2.get(query)
        self.assertTrue(resp.ok)

        # Look for l3extSubnet
        found = False
        for item in resp.json()['imdata']:
            if 'l3extSubnet' in item:
                if item['l3extSubnet']['attributes']['ip'] == ip + '/32':
                    found = True
                    break
        if not found:
            return False
        return True

    def test_basic_add_endpoint(self):
        """
        Test add endpoint
        """
        args = self.get_args()
        config = self.create_config_file_before()
        self.write_config_file(config, args)
        collector = execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        time.sleep(2)
        self.assertFalse(self.verify_remote_site_has_entry_before(mac, ip))

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry_before(mac, ip))
        config = self.create_config_file_after()
        self.write_config_file(config, args)
        collector.reload_config()
        time.sleep(4)
        self.assertTrue(self.verify_remote_site_has_entry_after(mac, ip))

    def test_basic_add_multiple_endpoint(self):
        """
        Test adding multiple endpoints
        """
        args = self.get_args()
        config = self.create_config_file_before()
        self.write_config_file(config, args)
        collector = execute_tool(args, test_mode=True)

        time.sleep(2)
        mac1 = '00:11:22:33:33:34'
        ip1 = '3.4.3.5'
        self.add_endpoint(mac1, ip1, 'intersite-testsuite', 'app', 'epg')
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry_before(mac1, ip1))
        self.assertTrue(self.verify_remote_site_has_entry_before(mac2, ip2))

        config = self.create_config_file_after()
        self.write_config_file(config, args)
        collector.reload_config()
        time.sleep(2)
        self.assertTrue(self.verify_remote_site_has_entry_after(mac1, ip1))
        self.assertTrue(self.verify_remote_site_has_entry_after(mac2, ip2))


class TestChangeL3Out(BaseTestCase):
    """
    Tests for changing OutsideL3 interfaces
    """
    def setup_local_site(self):
        """
        Set up the local site
        """
        # create Tenant, App, EPG on site 1
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        app = AppProfile('app', tenant)
        epg = EPG('epg', app)

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite')
        l3out1 = OutsideL3('l3out1', tenant)
        l3out2 = OutsideL3('l3out2', tenant)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    @staticmethod
    def create_export_policy(l3out_name):
        """
        Create the export policy
        :param l3out_name: String containing the OutsideL3 name
        :return: Dictionary containing the export policy
        """
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": l3out_name,
                                        "tenant": "intersite-testsuite"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        return export_policy

    def create_config_file(self, l3out_name):
        """
        Create the configuration
        :param l3out_name: String containing the OutsideL3 name
        :return: Dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = self.create_export_policy(l3out_name)
        config['config'].append(export_policy)
        return config

    def test_basic_add_endpoint(self):
        """
        Basic test for adding endpoint
        """
        args = self.get_args()
        config = self.create_config_file('l3out1')
        self.write_config_file(config, args)
        collector = execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        time.sleep(2)
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        config = self.create_config_file('l3out2')
        self.write_config_file(config, args)
        collector.reload_config()
        time.sleep(4)

        self.assertFalse(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))

    def test_basic_add_endpoint_multiple_l3out(self):
        """
        Test adding endpoint with multiple OutsideL3 interfaces
        """
        args = self.get_args()
        config = self.create_config_file('l3out1')
        for policy in config['config']:
            if 'export' in policy:
                for site_policy in policy['export']['remote_sites']:
                    interface_policy = {"l3out": {"name": "l3out2",
                                                  "tenant": "intersite-testsuite"}}
                    site_policy['site']['interfaces'].append(interface_policy)
                policy['export']['remote_sites'].append(site_policy)
        self.write_config_file(config, args)
        collector = execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        time.sleep(2)
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))
        config = self.create_config_file('l3out2')
        self.write_config_file(config, args)
        collector.reload_config()
        time.sleep(4)

        self.assertFalse(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_policy('intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))

    def test_basic_add_multiple_endpoint(self):
        """
        Test adding multiple endopoints
        """
        args = self.get_args()
        config = self.create_config_file('l3out1')
        self.write_config_file(config, args)
        collector = execute_tool(args, test_mode=True)

        time.sleep(2)
        mac1 = '00:11:22:33:33:34'
        ip1 = '3.4.3.5'
        self.add_endpoint(mac1, ip1, 'intersite-testsuite', 'app', 'epg')
        mac2 = '00:11:22:33:33:35'
        ip2 = '3.4.3.6'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite', 'app', 'epg')
        time.sleep(2)

        self.assertTrue(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out1', 'intersite-testsuite-app-epg'))

        config = self.create_config_file('l3out2')
        self.write_config_file(config, args)
        collector.reload_config()
        time.sleep(2)
        self.assertTrue(self.verify_remote_site_has_entry(mac1, ip1, 'intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite', 'l3out2', 'intersite-testsuite-app-epg'))

# test basic install of a single EPG and 1 endpoint being pushed to other site
# test remove EPG from policy and that


class TestDuplicates(BaseTestCase):
    """
    Test duplicate existing entry on the remote site
    """
    def create_config_file(self):
        """
        Create the configuration file
        :return: dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite-local",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out",
                                        "tenant": "intersite-testsuite-remote"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def setup_local_site(self):
        """
        Set up the local site
        """
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-local')
        app = AppProfile('app', tenant)
        epg = EPG('epg', app)

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-remote')
        l3out = OutsideL3('l3out', tenant)
        epg = OutsideEPG('intersite-testsuite-app-epg', l3out)
        other_epg = OutsideEPG('other', l3out)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def teardown_local_site(self):
        """
        Tear down the local site
        """
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-local')
        tenant.mark_as_deleted()

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def teardown_remote_site(self):
        """
        Tear down the remote site
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-remote')
        tenant.mark_as_deleted()

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def add_remote_duplicate_entry(self, ip):
        """
        Add a remote entry
        :param ip: String containing the IP address
        :return: None
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-remote')
        l3out = OutsideL3('l3out', tenant)
        other_epg = OutsideEPG('other', l3out)
        subnet = OutsideNetwork(ip, other_epg)
        subnet.ip = ip + '/32'

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def test_basic_duplicate(self):
        """
        Test a basic duplicate entry scenario.  An existing entry exists on the remote site but on
        a different OutsideEPG on the same OutsideL3.
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out', 'intersite-testsuite-app-epg'))
        self.add_remote_duplicate_entry(ip)

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite-local', 'app', 'epg')

        time.sleep(2)
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out', 'intersite-testsuite-app-epg'))

    def test_basic_multiple_duplicate(self):
        """
        Test a basic multiple duplicate entry scenario.
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        for i in range(0, 5):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out', 'intersite-testsuite-app-epg'))
            self.add_remote_duplicate_entry(ip)

        time.sleep(2)

        for i in range(0, 5):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.add_endpoint(mac, ip, 'intersite-testsuite-local', 'app', 'epg')

        time.sleep(2)
        for i in range(0, 5):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out', 'intersite-testsuite-app-epg'))

    def test_basic_partial_duplicate(self):
        """
        Test a basic multiple duplicate entry scenario where some of the entries in the set being added are duplicate.
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        for i in range(0, 7):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out', 'intersite-testsuite-app-epg'))
            self.add_remote_duplicate_entry(ip)

        time.sleep(2)

        for i in range(4, 9):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.add_endpoint(mac, ip, 'intersite-testsuite-local', 'app', 'epg')

        time.sleep(2)
        for i in range(4, 9):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out', 'intersite-testsuite-app-epg'))


class SetupDuplicateTests(BaseTestCase):
    """
    Base class to setup the duplicate tests
    """
    def create_config_file(self):
        """
        Create the configuration file
        :return: dictionary containing the configuration
        """
        config = self.create_site_config()
        export_policy = {
            "export": {
                "tenant": "intersite-testsuite-local",
                "app": "app",
                "epg": "epg",
                "remote_epg": "intersite-testsuite-app-epg",
                "remote_sites": [
                    {
                        "site": {
                            "name": "Site2",
                            "interfaces": [
                                {
                                    "l3out": {
                                        "name": "l3out1",
                                        "tenant": "intersite-testsuite-remote"
                                    }
                                },
                                {
                                    "l3out": {
                                        "name": "l3out2",
                                        "tenant": "intersite-testsuite-remote"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        config['config'].append(export_policy)
        return config

    def setup_local_site(self):
        """
        Set up the local site
        """
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-local')
        app = AppProfile('app', tenant)
        epg = EPG('epg', app)

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def setup_remote_site(self):
        """
        Set up the remote site
        """
        # Create tenant, L3out with contract on site 2
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-remote')
        l3out1 = OutsideL3('l3out1', tenant)
        l3out2 = OutsideL3('l3out2', tenant)
        epg1 = OutsideEPG('intersite-testsuite-app-epg', l3out1)
        other_epg = OutsideEPG('other', l3out1)
        epg2 = OutsideEPG('intersite-testsuite-app-epg', l3out2)

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def teardown_local_site(self):
        """
        Tear down the local site
        """
        site1 = Session(SITE1_URL, SITE1_LOGIN, SITE1_PASSWORD)
        resp = site1.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-local')
        tenant.mark_as_deleted()

        resp = tenant.push_to_apic(site1)
        self.assertTrue(resp.ok)

    def teardown_remote_site(self):
        """
        Tear down the remote site
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-remote')
        tenant.mark_as_deleted()

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)


class TestDuplicatesTwoL3Outs(SetupDuplicateTests):
    """
    Test duplicate entries with 2 OutsideL3 interfaces on the remote site
    """
    def add_remote_duplicate_entry(self, ip):
        """
        Add a remote entry
        :param ip: String containing the IP address
        :return: None
        """
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)

        tenant = Tenant('intersite-testsuite-remote')
        l3out = OutsideL3('l3out1', tenant)
        other_epg = OutsideEPG('other', l3out)
        subnet = OutsideNetwork(ip, other_epg)
        subnet.ip = ip + '/32'

        resp = tenant.push_to_apic(site2)
        self.assertTrue(resp.ok)

    def test_basic_duplicate(self):
        """
        Test a basic duplicate entry scenario.  An existing entry exists on the remote site but on
        a different OutsideEPG on the same OutsideL3.
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out1', 'intersite-testsuite-app-epg'))
        self.add_remote_duplicate_entry(ip)

        time.sleep(2)
        self.add_endpoint(mac, ip, 'intersite-testsuite-local', 'app', 'epg')
        mac2 = '00:11:22:33:33:44'
        ip2 = '3.4.3.44'
        self.add_endpoint(mac2, ip2, 'intersite-testsuite-local', 'app', 'epg')

        time.sleep(2)
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite-remote', 'l3out1', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out2', 'intersite-testsuite-app-epg'))
        self.assertTrue(self.verify_remote_site_has_entry(mac2, ip2, 'intersite-testsuite-remote', 'l3out2', 'intersite-testsuite-app-epg'))

    def test_basic_multiple_duplicate(self):
        """
        Test a basic multiple duplicate entry scenario.
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        for i in range(0, 5):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out1', 'intersite-testsuite-app-epg'))
            self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out2', 'intersite-testsuite-app-epg'))
            self.add_remote_duplicate_entry(ip)

        time.sleep(2)

        for i in range(0, 5):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.add_endpoint(mac, ip, 'intersite-testsuite-local', 'app', 'epg')

        time.sleep(2)
        for i in range(0, 5):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out1', 'intersite-testsuite-app-epg'))
            self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out2', 'intersite-testsuite-app-epg'))

    def test_basic_partial_duplicate(self):
        """
        Test a basic multiple duplicate entry scenario where some of the entries in the set being added are duplicate.
        """
        args = self.get_args()
        config = self.create_config_file()
        self.write_config_file(config, args)
        execute_tool(args, test_mode=True)

        for i in range(0, 7):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out1', 'intersite-testsuite-app-epg'))
            self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out2', 'intersite-testsuite-app-epg'))
            self.add_remote_duplicate_entry(ip)

        time.sleep(2)

        for i in range(4, 9):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.add_endpoint(mac, ip, 'intersite-testsuite-local', 'app', 'epg')

        time.sleep(2)
        for i in range(4, 9):
            mac = '00:11:22:33:33:3' + str(i)
            ip = '3.4.3.' + str(i)
            self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out1', 'intersite-testsuite-app-epg'))
            self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite-remote', 'l3out2', 'intersite-testsuite-app-epg'))


class TestDeletions(BaseEndpointTestCase):
    """
    Tests for deletion of stale entries
    """
    def test_basic_deletion(self):
        """
        Test basic deletion of a stale entry on tool startup
        :return:
        """
        args = self.get_args()
        config_filename = 'testsuite_cfg.json'
        args.config = config_filename
        config = self.create_config_file()

        config_file = open(config_filename, 'w')
        config_file.write(str(json.dumps(config)))
        config_file.close()

        # Create the "stale" entry on the remote site
        mac = '00:11:22:33:33:33'
        ip = '3.4.3.4'
        site2 = Session(SITE2_URL, SITE2_LOGIN, SITE2_PASSWORD)
        resp = site2.login()
        self.assertTrue(resp.ok)
        tag = IntersiteTag('intersite-testsuite', 'app', 'epg', 'Site1')
        remote_tenant = Tenant('intersite-testsuite')
        remote_l3out = OutsideL3('l3out', remote_tenant)
        remote_epg = OutsideEPG('intersite-testsuite-app-epg', remote_l3out)
        remote_ep = OutsideNetwork(ip, remote_epg)
        remote_ep.ip = ip + '/32'
        remote_tenant.push_to_apic(site2)

        time.sleep(2)
        self.assertTrue(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))

        execute_tool(args, test_mode=True)

        time.sleep(2)
        self.assertFalse(self.verify_remote_site_has_entry(mac, ip, 'intersite-testsuite', 'l3out', 'intersite-testsuite-app-epg'))


def main_test():
    """
    Main execution routine.  Create the test suites and run.
    """
    full = unittest.TestSuite()
    full.addTest(unittest.makeSuite(TestToolOptions))
    full.addTest(unittest.makeSuite(TestBadConfiguration))
    full.addTest(unittest.makeSuite(TestBasicEndpoints))
    full.addTest(unittest.makeSuite(TestMultipleEPG))
    full.addTest(unittest.makeSuite(TestBasicExistingEndpoints))
    full.addTest(unittest.makeSuite(TestBasicExistingEndpointsAddPolicyLater))
    full.addTest(unittest.makeSuite(TestExportPolicyRemoval))
    full.addTest(unittest.makeSuite(TestBasicEndpointsWithContract))
    full.addTest(unittest.makeSuite(TestBasicEndpointMove))
    full.addTest(unittest.makeSuite(TestPolicyChangeProvidedContract))
    full.addTest(unittest.makeSuite(TestChangeL3Out))
    full.addTest(unittest.makeSuite(TestDuplicates))
    full.addTest(unittest.makeSuite(TestDuplicatesTwoL3Outs))
    full.addTest(unittest.makeSuite(TestDeletions))

    unittest.main()


if __name__ == '__main__':
    try:
        main_test()
    except KeyboardInterrupt:
        pass
