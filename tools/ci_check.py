"""Run public-only static validation and a nonempty unittest suite."""
from pathlib import Path
import re
import sys
import unittest
import yaml
import jinja2
from privacy_guard import validate


def main():
    root=Path(__file__).resolve().parents[1]
    validate(root)
    sys.path.insert(0,str(root/'ansible/scripts'))
    import ipam
    yaml_count=template_count=0
    for p in root.rglob('*'):
        if '.git' in p.parts or '__pycache__' in p.parts or not p.is_file(): continue
        if p.suffix in ('.yml','.yaml'):
            yaml.load(p.read_text(encoding='utf-8'),Loader=ipam.UniqueLoader)
            yaml_count+=1
        elif p.suffix=='.j2':
            jinja2.Environment().parse(p.read_text(encoding='utf-8'))
            template_count+=1
        elif p.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                if '://' not in target and not target.startswith('#') and not (p.parent/target.split('#')[0]).exists():
                    raise ValueError(f'broken document link: {p.name}')
    for environment in ('prod','stg','dev'):
        directory=root/'ansible/inventories'/environment
        n,h,r=[ipam.load(directory/f) for f in ('ipam/networks.yml','ipam/reservations.yml','guest_resources.yml')]
        ipam.validate(n,h,r,environment)
        if ipam.inventory(n,h,r,environment)!=ipam.load(directory/'hosts.yml'):
            raise ValueError('generated sample inventory differs')
    ipam.validate_all(root/'ansible/inventories')
    suite=unittest.TestSuite()
    for directory in ('ansible/tests','tests'):
        group=unittest.defaultTestLoader.discover(str(root/directory),pattern='test_*.py',top_level_dir=str(root/directory))
        if group.countTestCases()==0: raise ValueError(f'zero tests in required group: {directory}')
        suite.addTests(group)
    count=suite.countTestCases()
    if count<28: raise ValueError('required test inventory is incomplete')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(f'Executed tests: {count}; YAML: {yaml_count}; templates: {template_count}')
    return 0 if result.wasSuccessful() and result.testsRun==count and not result.skipped else 1


if __name__=='__main__': raise SystemExit(main())
