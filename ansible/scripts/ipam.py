#!/usr/bin/env python3
"""Offline IPAM validation and deterministic inventory generation. No API writes."""
import argparse
import ipaddress
from pathlib import Path
import re
import sys
import yaml


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load(path):
    value = yaml.load(Path(path).read_text(encoding='utf-8-sig'), Loader=UniqueLoader)
    if not isinstance(value, dict):
        raise ValueError(f'{path}: expected mapping')
    return value


def require(condition, message):
    if not condition:
        raise ValueError(message)


def expected_vmid(ipv4, environment):
    octets = str(ipaddress.IPv4Address(ipv4)).split('.')
    base = octets[2] + octets[3]
    return int({'prod': '', 'stg': '2', 'dev': '3'}[environment] + base)


def validate(networks, reservations, resources, environment, draft=False):
    warnings = []
    require(environment in ('dev', 'stg', 'prod'), 'unknown environment')
    if not networks or not reservations:
        require(draft, 'empty IPAM cannot be deployed')
        warnings.append('empty environment: define isolated networks and hosts before deployment')
    parsed = {}
    seen_subnets, subnet_ids = [], set()
    for name, n in networks.items():
        require(name in ('edge','app','db','monitoring','security','game'), f'unknown network: {name}')
        require(isinstance(n, dict) and set(n) == {'subnet','gateway','bridge','vlan','kea','dns'}, f'{name}: network schema')
        require(isinstance(n['kea'], dict) and set(n['kea']) == {'subnet_id','reservation_start','reservation_end','dynamic_pool'}, f'{name}: Kea schema')
        require(isinstance(n['dns'], dict) and set(n['dns']) == {'domain'}, f'{name}: DNS schema')
        subnet=ipaddress.IPv4Network(n['subnet'], strict=True)
        segment = {'edge': 1, 'app': 2, 'db': 3, 'monitoring': 4, 'security': 5, 'game': 100}[name]
        environment_octet = {'prod': 80, 'stg': 81, 'dev': 82}[environment]
        bridge_offset = {'prod': 0, 'stg': 10, 'dev': 20}[environment]
        require(str(subnet) == f'10.{environment_octet}.{segment}.0/24', f'{name}: environment subnet mismatch')
        require(n['bridge'] == f'vmbr{segment + bridge_offset}', f'{name}: environment bridge mismatch')
        gateway=ipaddress.IPv4Address(n['gateway'])
        start=ipaddress.IPv4Address(n['kea']['reservation_start'])
        end=ipaddress.IPv4Address(n['kea']['reservation_end'])
        require(subnet.prefixlen == 24, f'{name}: expected /24')
        require(all(x in subnet and x not in (subnet.network_address,subnet.broadcast_address) for x in (gateway,start,end)), f'{name}: invalid subnet addresses')
        require(start <= end and not start <= gateway <= end, f'{name}: invalid reservation range')
        require(gateway == subnet.network_address+1 and start == subnet.network_address+10 and end == subnet.network_address+199, f'{name}: v0.17 range/gateway mismatch')
        require(not any(subnet.overlaps(x) for x in seen_subnets), f'{name}: overlapping subnet')
        seen_subnets.append(subnet)
        sid=n['kea']['subnet_id']
        require(type(sid) is int and sid > 0 and sid not in subnet_ids, f'{name}: invalid/duplicate subnet_id')
        subnet_ids.add(sid)
        require(n['kea']['dynamic_pool'] is None, f'{name}: dynamic pool is outside initial design')
        require(isinstance(n['bridge'],str) and re.fullmatch(r'vmbr[0-9]+',n['bridge']), f'{name}: invalid bridge')
        require(n['vlan'] is None or type(n['vlan']) is int and 1 <= n['vlan'] <= 4094, f'{name}: invalid VLAN')
        require(n['dns']['domain']=='internal.example.invalid', f'{name}: invalid internal domain')
        parsed[name]=(subnet,gateway,start,end)
    seen = {k:set() for k in ('hostname','vmid','ipv4','mac')}
    require(set(resources)==set(reservations), 'resource and reservation host sets differ')
    for hostname,h in reservations.items():
        require(isinstance(hostname,str) and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',hostname), 'invalid hostname')
        require(hostname.startswith(environment+'-'), f'{hostname}: wrong environment prefix')
        require(isinstance(h,dict) and set(h)=={'vmid','network','mac','ipv4','dns_enabled','description','owner','state'}, f'{hostname}: reservation schema')
        require(type(h['vmid']) is int and 100 <= h['vmid'] <= 999999999, f'{hostname}: invalid VMID')
        require(h['network'] in parsed, f'{hostname}: unknown network')
        require(type(h['dns_enabled']) is bool, f'{hostname}: dns_enabled must be boolean')
        require(h['state'] in ('present','disabled'), f'{hostname}: invalid state')
        require(all(isinstance(h[k],str) and h[k].strip() for k in ('description','owner')), f'{hostname}: missing description/owner')
        ip=ipaddress.IPv4Address(h['ipv4'])
        subnet,gateway,start,end=parsed[h['network']]
        require(ip in subnet and ip not in (gateway,subnet.network_address,subnet.broadcast_address) and start <= ip <= end, f'{hostname}: invalid reservation IPv4')
        require(h['vmid']==expected_vmid(ip,environment), f'{hostname}: VMID naming rule')
        mac=h['mac']
        if mac is None:
            require(draft, f'{hostname}: MAC is not confirmed')
            warnings.append(f'{hostname}: MAC is not confirmed')
        else:
            require(isinstance(mac,str) and re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',mac), f'{hostname}: invalid MAC')
            require(not int(mac[:2],16)&1 and mac.lower()!='00:00:00:00:00:00', f'{hostname}: multicast/zero MAC')
        for key,value in [('hostname',hostname.lower()),('vmid',h['vmid']),('ipv4',str(ip)),('mac',mac.lower() if mac else None)]:
            if value is not None:
                require(value not in seen[key], f'duplicate {key}: {value}')
                seen[key].add(value)
        r=resources[hostname]
        require(isinstance(r,dict) and not set(r)&{'vmid','network','mac','ip','ipv4','bridge','gateway','vlan'}, f'{hostname}: IPAM fields duplicated in resources')
        require(r.get('kind') in ('qemu','lxc'), f'{hostname}: invalid guest kind')
        for key in ('cores','memory_mb','disk_gb','onboot_order'):
            require(type(r.get(key)) is int and r[key]>0, f'{hostname}: invalid resource {key}')
        require(isinstance(r.get('groups'),list) and r['groups'] and all(g in GROUPS for g in r['groups']), f'{hostname}: invalid groups')
    return warnings


def validate_all(inventories):
    """Check shared-PVE VMIDs, global MAC uniqueness, and L2/L3 isolation."""
    seen = {'vmid': {}, 'mac': {}, 'ipv4': {}, 'bridge': {}, 'subnet': {}}
    pending = []
    def unique(key, value, label):
        if value is None:
            pending.append(f'{label}: missing {key}')
            return
        normalized = value.lower() if isinstance(value,str) else value
        require(normalized not in seen[key], f'cross-environment duplicate {key}: {value}')
        seen[key][normalized] = label
    for environment in ('dev','stg','prod'):
        directory = Path(inventories)/environment
        networks = load(directory/'ipam/networks.yml')
        hosts = load(directory/'ipam/reservations.yml')
        validate(networks,hosts,load(directory/'guest_resources.yml'),environment)
        for role, network in networks.items():
            for key in ('bridge','subnet'): unique(key,network[key],environment+'/'+role)
        for hostname,host in hosts.items():
            for key in ('vmid','mac','ipv4'): unique(key,host[key],hostname)
        for name,host in load(directory/'ipam/infrastructure.yml').items():
            require(host.get('reservation_managed') is False, f'{name}: infrastructure must not use DHCP reservation')
            require(host.get('vmid') is None or type(host['vmid']) is int and 100 <= host['vmid'] <= 999999999, f'{name}: invalid infrastructure VMID')
            unique('vmid',host.get('vmid'),environment+'/'+name)
    bootstrap = load(Path(inventories).parent/'bootstrap/required-inputs.yml')
    runner = bootstrap['nonprod_runner']
    for key in ('vmid','ipv4'): unique(key,runner.get(key),'nonprod_runner')
    return pending


GROUPS=('caddy_servers','nextcloud_servers','imaginary_servers','onlyoffice_servers',
        'mariadb_servers','valkey_servers','grafana_servers','zabbix_servers',
        'loki_servers','prometheus_servers','runner_servers')


def inventory(networks, reservations, resources, environment):
    children={'pve_nodes':{'hosts':{'pve1':{'ansible_host':'{{ pve_ssh_host }}','ansible_user':'ansible'}}}}
    for g in GROUPS: children[g]={'hosts':{}}
    guests=[]
    for name,h in reservations.items():
        if h['state']!='present': continue
        r=resources[name]; n=networks[h['network']]
        for g in r['groups']: children[g]['hosts'][name]={'ansible_host':h['ipv4']}
        guests.append({**{k:v for k,v in r.items() if k!='groups'},'name':name,'vmid':h['vmid'],
                       'mac':h['mac'],'ip':h['ipv4'],'bridge':n['bridge'],'gateway':n['gateway'],'vlan':n['vlan']})
    children['docker_hosts']={'children':{g:{} for g in ('imaginary_servers','onlyoffice_servers','grafana_servers','zabbix_servers','loki_servers','prometheus_servers')}}
    children['managed_linux']={'children':{g:{} for g in GROUPS}}
    return {'all':{'vars':{'ansible_user':'ansible','pve_guests':guests},'children':children}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory',type=Path)
    parser.add_argument('--draft',action='store_true',help='permit missing MACs and empty environments; never deploy')
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--check-generated',action='store_true')
    parser.add_argument('--check-all',action='store_true',help='validate all environments under inventories')
    args=parser.parse_args()
    try:
        if args.check_all:
            require(not (args.draft or args.render or args.check_generated), '--check-all cannot be combined with other modes')
            for item in validate_all(args.inventory): print('INPUT_REQUIRED: '+item)
            print('Cross-environment static IPAM validation passed; infrastructure inputs still require preflight')
            return 0
        networks=load(args.inventory/'ipam/networks.yml')
        reservations=load(args.inventory/'ipam/reservations.yml')
        resources=load(args.inventory/'guest_resources.yml')
        warnings=validate(networks,reservations,resources,args.inventory.name,args.draft)
        expected=inventory(networks,reservations,resources,args.inventory.name)
        if args.check_generated:
            require(load(args.inventory/'hosts.yml')==expected,'hosts.yml differs from authoritative IPAM/resources; regenerate')
        if args.render:
            (args.inventory/'hosts.yml').write_text('# GENERATED by scripts/ipam.py; edit IPAM/resources instead.\n'+yaml.safe_dump(expected,allow_unicode=True,sort_keys=False),encoding='utf-8',newline='\n')
        for warning in warnings: print('WARNING: '+warning)
        print(f'{args.inventory.name}: {len(reservations)} hosts validated'+(' (DRAFT ONLY)' if args.draft else ''))
        return 0
    except (ValueError,TypeError,KeyError,OSError,yaml.YAMLError) as exc:
        print(f'IPAM ERROR: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
