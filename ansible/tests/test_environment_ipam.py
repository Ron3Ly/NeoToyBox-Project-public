from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import ipam


class EnvironmentIPAMTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def environment(self, name):
        d = self.root/'inventories'/name
        return [ipam.load(d/p) for p in ('ipam/networks.yml','ipam/reservations.yml','guest_resources.yml')]

    def test_prefix_examples(self):
        self.assertEqual(ipam.expected_vmid('10.80.2.10','prod'),210)
        self.assertEqual(ipam.expected_vmid('10.82.2.10','dev'),3210)
        self.assertEqual(ipam.expected_vmid('10.82.100.10','dev'),310010)

    def test_old_dev_suffix_rejected(self):
        n,h,r = self.environment('dev')
        h['dev-nc-lxc']['vmid'] = 2101
        with self.assertRaisesRegex(ValueError,'VMID naming rule'):
            ipam.validate(n,h,r,'dev')

    def test_prod_network_not_accepted_in_dev(self):
        n,h,r = self.environment('dev')
        n['app']['subnet'] = '10.80.2.0/24'
        with self.assertRaisesRegex(ValueError,'environment subnet'):
            ipam.validate(n,h,r,'dev')

    def test_bridge_must_match_environment(self):
        n,h,r = self.environment('dev')
        n['app']['bridge'] = 'vmbr2'
        with self.assertRaisesRegex(ValueError,'environment bridge'):
            ipam.validate(n,h,r,'dev')

    def test_dev_is_valid_and_runner_is_external(self):
        n,h,r = self.environment('dev')
        self.assertEqual(ipam.validate(n,h,r,'dev'),[])
        generated = ipam.inventory(n,h,r,'dev')
        self.assertEqual(generated['all']['children']['runner_servers']['hosts'],{})
        present = {name for name, host in h.items() if host['state'] == 'present'}
        self.assertEqual({guest['name'] for guest in generated['all']['vars']['pve_guests']}, present)

    def test_current_cross_environment_state(self):
        pending = ipam.validate_all(self.root/'inventories')
        self.assertTrue(any('nonprod_runner' in item for item in pending))

    def fixture(self, temp):
        p=Path(temp)
        shutil.copytree(self.root/'inventories',p/'inventories')
        shutil.copytree(self.root/'bootstrap',p/'bootstrap')
        return p/'inventories'

    def test_cross_environment_mac_duplicate(self):
        with tempfile.TemporaryDirectory() as t:
            inventories=self.fixture(t)
            prod=ipam.load(inventories/'prod/ipam/reservations.yml')
            path=inventories/'dev/ipam/reservations.yml'
            dev=ipam.load(path)
            dev['dev-nc-lxc']['mac']=prod['prod-nc-lxc']['mac']
            path.write_text(ipam.yaml.safe_dump(dev),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'cross-environment duplicate mac'):
                ipam.validate_all(inventories)

    def test_infrastructure_vmid_collision_on_dev_pve(self):
        with tempfile.TemporaryDirectory() as t:
            inventories=self.fixture(t)
            path=inventories/'dev/ipam/infrastructure.yml'
            data=ipam.load(path)
            data['opnsense']['vmid']=ipam.load(inventories/'dev/ipam/reservations.yml')['dev-nc-lxc']['vmid']
            path.write_text(ipam.yaml.safe_dump(data),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'duplicate vmid'):
                ipam.validate_all(inventories)

    def test_duplicate_infrastructure_vmid_across_environments(self):
        with tempfile.TemporaryDirectory() as t:
            inventories = self.fixture(t)
            path = inventories/'dev/ipam/infrastructure.yml'
            dev = ipam.load(path)
            prod = ipam.load(inventories/'prod/ipam/infrastructure.yml')
            dev['opnsense']['vmid'] = prod['opnsense']['vmid']
            path.write_text(ipam.yaml.safe_dump(dev), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'cross-environment duplicate vmid'):
                ipam.validate_all(inventories)


if __name__=='__main__': unittest.main()
