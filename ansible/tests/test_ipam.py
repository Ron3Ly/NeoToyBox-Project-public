import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ipam


class IPAMTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'inventories/prod'
        self.n=ipam.load(root/'ipam/networks.yml')
        self.h=ipam.load(root/'ipam/reservations.yml')
        self.r=ipam.load(root/'guest_resources.yml')
        # Synthetic values exist only in memory as test fixtures, never in the inventory.
        for i,h in enumerate(self.h.values()): h['mac']=f'02:00:00:00:00:{i+1:02x}'
        self.first,self.second=list(self.h)[:2]

    def validate(self): return ipam.validate(self.n,self.h,self.r,'prod')

    def test_valid_and_gls_consolidation(self):
        self.validate()
        inv=ipam.inventory(self.n,self.h,self.r,'prod')['all']['children']
        for group in ('grafana_servers','loki_servers','prometheus_servers'):
            self.assertEqual(list(inv[group]['hosts']),['prod-gls-vm'])

    def test_invalid_addresses(self):
        for address in ('10.80.1.0','10.80.1.1','10.80.1.255','10.80.1.200','10.80.2.10','300.1.1.1','::1'):
            with self.subTest(address=address),self.assertRaises(ValueError):
                self.h[self.first]['ipv4']=address
                self.validate()

    def test_duplicate_mac(self):
        self.h[self.second]['mac']=self.h[self.first]['mac']
        with self.assertRaisesRegex(ValueError,'duplicate mac'): self.validate()

    def test_duplicate_ip_and_vmid(self):
        self.h[self.second]=copy.deepcopy(self.h[self.first])
        self.h[self.second]['mac']='02:00:00:00:00:ff'
        with self.assertRaisesRegex(ValueError,'duplicate vmid'): self.validate()

    def test_duplicate_yaml_hostname(self):
        with self.assertRaisesRegex(ValueError,'duplicate YAML key'):
            ipam.yaml.load('host: 1\nhost: 2\n',Loader=ipam.UniqueLoader)

    def test_missing_mac_strict_vs_draft(self):
        self.h[self.first]['mac']=None
        with self.assertRaisesRegex(ValueError,'MAC is not confirmed'): self.validate()
        self.assertTrue(ipam.validate(self.n,self.h,self.r,'prod',True))

    def test_invalid_macs(self):
        for mac in ('invalid','ff:ff:ff:ff:ff:ff','00:00:00:00:00:00',123):
            with self.subTest(mac=mac),self.assertRaises(ValueError):
                self.h[self.first]['mac']=mac
                self.validate()

    def test_unknown_network(self):
        self.h[self.first]['network']='unknown'
        with self.assertRaisesRegex(ValueError,'unknown network'): self.validate()

    def test_boolean_type(self):
        self.h[self.first]['dns_enabled']='true'
        with self.assertRaisesRegex(ValueError,'boolean'): self.validate()

    def test_disabled_not_rendered(self):
        self.h[self.first]['state']='disabled'
        self.validate()
        guests=ipam.inventory(self.n,self.h,self.r,'prod')['all']['vars']['pve_guests']
        self.assertNotIn(self.first,[g['name'] for g in guests])

    def test_empty_environment_not_deployable(self):
        with self.assertRaisesRegex(ValueError,'empty IPAM'): ipam.validate({},{},{},'dev')
        self.assertTrue(ipam.validate({},{},{},'dev',True))

    def test_normalization(self):
        self.r[self.first]['ip']='10.80.1.10'
        with self.assertRaisesRegex(ValueError,'duplicated in resources'): self.validate()


if __name__=='__main__': unittest.main()
