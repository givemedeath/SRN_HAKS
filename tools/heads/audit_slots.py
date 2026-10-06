"""Audit the user-declared installed game/repository stack and persist 200 slots."""
import argparse
from pathlib import Path
import struct
from head_workflow import allocate_slots, pin, read, require, verify_pins, write_fresh


KEY_TYPES = {3: '.tga', 6: '.plt', 2002: '.mdl', 2022: '.txi', 2033: '.dds', 2072: '.mtr'}


def installed_resources(root):
    """Read current installed resource names without activating user overrides."""
    root = Path(root).resolve()
    keys = sorted((root / 'data').rglob('*.key'))
    require(keys, 'Installed game KEY indexes required')
    resources = set()
    for path in keys:
        data = path.read_bytes()
        require(len(data) >= 64 and data[:8] == b'KEY V1  ', 'Invalid installed KEY index')
        count, offset = struct.unpack_from('<I', data, 12)[0], struct.unpack_from('<I', data, 20)[0]
        require(offset >= 64 and offset + count * 22 <= len(data), 'Installed KEY resource table bounds invalid')
        for index in range(count):
            name, kind, identity = struct.unpack_from('<16sHI', data, offset + index * 22)
            if kind in KEY_TYPES:
                resources.add(name.split(b'\0')[0].decode('ascii').lower() + KEY_TYPES[kind])
    return resources, keys


def repository_resources(repository, config):
    resources, files, packs = set(), [], []
    for pack in config['HakList']:
        folder = (repository / pack['Path']).resolve()
        require(folder.is_relative_to(repository) and folder.is_dir(), 'Declared HAK source missing or outside checkout')
        members = sorted(path for path in folder.rglob('*') if path.is_file() and not path.name.startswith('.'))
        require(members, 'Declared pack is empty')
        resources.update(path.name.lower() for path in members)
        files.extend(members)
        packs.append({'name': pack['Name'], 'resources': len(members)})
    return resources, files, packs


def verify_publication_inventory(audit_path, repository, roster, selected_resources):
    audit = read(audit_path)
    repository = Path(repository).resolve()
    require(audit.get('kind') == 'srn-head-slot-audit' and audit.get('complete') is True
            and audit.get('consumerScope') == 'installed-game-and-repository-packs', 'Complete current slot audit required')
    require(audit.get('repository') == str(repository) and audit.get('installedRoot'),
            'Legacy or mismatched slot audit; re-audit with the installed root before publication')
    verify_pins(audit['inputs'])
    require(read(audit['engineRangeProof']['path'])['Appearance_Head']['type'] == 'byte', 'Installed head range proof required')
    config_path = repository / 'hakbuilder.json'
    require(audit['hakConfiguration'] == pin(config_path), 'Consumer HAK configuration changed; re-audit')
    installed, keys = installed_resources(audit['installedRoot'])
    current, files, packs = repository_resources(repository, read(config_path))
    occupied = installed | current | {name.lower() for name in read(audit['installedInventory']['path'])}
    # Enumerate membership again: pinning old files alone misses new collisions.
    require(allocate_slots(roster, occupied, maximum=audit['maximum']) == roster,
            'Publication slot allocation differs from the current consumer stack')
    require(not (set(selected_resources) & occupied), 'Publication resource now collides with the consumer stack')


def audit(installed, proof, hak_config, repository, roster, output, allocated, *, installed_root):
    repository=Path(repository).resolve()
    require(read(proof)["Appearance_Head"]["type"] == "byte", "Installed BIC head BYTE proof required")
    config=read(hak_config)
    live_installed, keys = installed_resources(installed_root)
    current, files, packs = repository_resources(repository, config)
    resources = set(read(installed)) | live_installed | current
    inputs=[pin(installed),pin(proof),pin(hak_config),*[pin(path) for path in keys + files]]
    audit={"schemaVersion":2,"kind":"srn-head-slot-audit","complete":True,
           "repository":str(repository), "installedRoot":str(Path(installed_root).resolve()),
           "hakConfiguration":pin(hak_config), "installedInventory":pin(installed),
           "consumerScope":"installed-game-and-repository-packs","maximum":255,
           "engineRangeProof":pin(proof),"inputs":inputs,"resources":sorted(set(resources)),"packs":packs,
           "rangeMeaning":"NWN installed BIC Appearance_Head uses BYTE (0..255); pipeline reserves 0. Actual client selectability remains a separate gate."}
    result=allocate_slots(read(roster),resources,maximum=255)
    write_fresh(output,audit); write_fresh(allocated,result)
    return audit


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("installed","proof","hak-config","repository","roster","output","allocated"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument('--installed-root', type=Path, required=True)
    args=parser.parse_args(); audit(args.installed,args.proof,args.hak_config,args.repository,args.roster,args.output,args.allocated,
                                  installed_root=args.installed_root)
