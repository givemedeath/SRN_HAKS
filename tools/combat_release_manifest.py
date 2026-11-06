"""Build the SR_NWN Phase 2A combat-slice release manifest for SRN_HAKS weapons.

The manifest is an inventory of tracked content and its dependency closure. It
grants no asset, rights, client or production approval.

Usage:
  python tools/combat_release_manifest.py            # write docs/items/combat-2a-release-manifest-v1.{json,md}
  python tools/combat_release_manifest.py --check    # fail if the tracked manifest is stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = Path('docs/items/combat-2a-release-manifest-v1.json')
MD_OUT = Path('docs/items/combat-2a-release-manifest.md')
PUBLICATION = Path('docs/items/approved-weapons-v1.json')
VALIDATION = Path('docs/items/approved-weapon-waves-release-validation.json')
FIREARM_GRIP = Path('docs/items/firearm-grip-standard-v1.json')
BLADE_GRIP = Path('docs/items/weapon-grip-standard-v1.json')
BASEITEMS = Path('srn_2da/baseitems.2da')
# Pack files are split so the test-impact catalog tracks srn_tlk as a pack reference, which stays the same in
# sparse CI checkouts that omit pack folders.
TLK = Path('srn_tlk', 'srn.tlk.json')
ALLOCATIONS = Path('srn_tlk', 'allocations.json')
MDRNEE_ITEMS = Path('docs/imports/mdrnee_item-manifest.json')
MDRNEE_MIGRATION = Path('docs/imports/mdrnee_item-migration-manifest.json')
HAKBUILDER = Path('hakbuilder.json')
WEAPON_PACK = 'srn_weapon'
TEXTURE_SUFFIXES = ('.tga', '.dds', '.plt')
TABLE_PACK = 'srn_2da'
PINNED_COMMIT = '53948783596331a15ec300a28ae824993c7aa812'
TLK_CUSTOM_BASE = 0x01000000
NO_STRREF = 0xFFFFFFFF
BASEITEM_STRREF_COLUMNS = ('Name', 'Description', 'BaseItemStatRef')
BASEITEM_COLUMNS = ('label', 'ModelType', 'ItemClass', 'MinRange', 'MaxRange', 'DefaultModel',
                    'DefaultIcon', 'WeaponWield', 'WeaponType', 'WeaponSize', 'RangedWeapon',
                    'AmmunitionType', 'NumDice', 'DieToRoll', 'CritThreat', 'CritHitMult',
                    'BaseCost', 'ReqFeat0', 'ReqFeat1', 'ReqFeat2', 'ReqFeat3', 'ReqFeat4',
                    *BASEITEM_STRREF_COLUMNS)
SLING_ROW = 61
RESOURCE_TYPES = {'.mdl': 2002, '.tga': 3, '.uti': 2025}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.as_posix()


def read(path: Path) -> bytes:
    return (ROOT / path).read_bytes()


def load_json(path: Path):
    return json.loads(read(path).decode('utf-8'))


# --- GFF V3.2 -------------------------------------------------------------------------------

def parse_gff(data: bytes) -> dict:
    if data[4:8] != b'V3.2':
        raise ValueError('unsupported GFF version')
    (s_off, s_cnt, f_off, f_cnt, l_off, l_cnt, d_off, _d_cnt, fi_off, _fi_cnt, li_off,
     _li_cnt) = struct.unpack_from('<12I', data, 8)
    labels = [data[l_off + 16 * i:l_off + 16 * (i + 1)].rstrip(b'\0').decode('ascii')
              for i in range(l_cnt)]

    def field(index: int):
        ftype, label, value = struct.unpack_from('<3I', data, f_off + 12 * index)
        raw = struct.pack('<I', value)
        if ftype in (0, 2, 4):
            out = value
        elif ftype == 1:
            out = struct.unpack('<b', raw[:1])[0]
        elif ftype == 3:
            out = struct.unpack('<h', raw[:2])[0]
        elif ftype == 5:
            out = struct.unpack('<i', raw)[0]
        elif ftype == 8:
            out = struct.unpack('<f', raw)[0]
        elif ftype in (6, 7, 9):
            out = struct.unpack_from({6: '<Q', 7: '<q', 9: '<d'}[ftype], data, d_off + value)[0]
        elif ftype == 10:
            size = struct.unpack_from('<I', data, d_off + value)[0]
            out = data[d_off + value + 4:d_off + value + 4 + size].decode('cp1252')
        elif ftype == 11:
            size = data[d_off + value]
            out = data[d_off + value + 1:d_off + value + 1 + size].decode('cp1252')
        elif ftype == 12:
            _total, strref, count = struct.unpack_from('<3I', data, d_off + value)
            pos, strings = d_off + value + 12, {}
            for _ in range(count):
                sid, size = struct.unpack_from('<iI', data, pos)
                strings[str(sid)] = data[pos + 8:pos + 8 + size].decode('cp1252')
                pos += 8 + size
            out = {'strRef': strref, 'strings': strings}
        elif ftype == 13:
            size = struct.unpack_from('<I', data, d_off + value)[0]
            out = {'voidBytes': size}
        elif ftype == 14:
            out = struct_at(value)
        elif ftype == 15:
            count = struct.unpack_from('<I', data, li_off + value)[0]
            out = [struct_at(i) for i in struct.unpack_from(f'<{count}I', data, li_off + value + 4)]
        else:
            raise ValueError(f'unsupported GFF field type {ftype}')
        return labels[label], out

    def struct_at(index: int) -> dict:
        _stype, value, count = struct.unpack_from('<3I', data, s_off + 12 * index)
        if count == 1:
            indices = [value]
        else:
            indices = list(struct.unpack_from(f'<{count}I', data, fi_off + value)) if count else []
        return dict(field(i) for i in indices)

    if s_cnt < 1 or f_cnt < 0:
        raise ValueError('empty GFF')
    return struct_at(0)


# --- 2DA V2.0 -------------------------------------------------------------------------------

def parse_2da(text: str) -> tuple[list[str], dict[int, dict[str, str]]]:
    lines = text.splitlines()
    if not lines or not lines[0].startswith('2DA V2.0'):
        raise ValueError('unsupported 2DA')
    body = [line for line in lines[1:] if line.strip()]
    if body and body[0].lstrip().startswith('DEFAULT:'):
        body = body[1:]
    tokens = lambda line: [t[1:-1] if t.startswith('"') else t for t in re.findall(r'"[^"]*"|\S+', line)]
    columns = tokens(body[0])
    rows = {}
    for line in body[1:]:
        values = tokens(line)
        rows[int(values[0])] = dict(zip(columns, values[1:] + ['****'] * (len(columns) + 1 - len(values))))
    return columns, rows


# --- Model texture references ---------------------------------------------------------------

def model_strings(data: bytes) -> set[str]:
    return {m.decode('ascii').lower() for m in re.findall(rb'([A-Za-z0-9_]{3,32})\x00', data)}


# --- Git ------------------------------------------------------------------------------------

def git_available(commit: str) -> bool:
    try:
        return subprocess.run(['git', 'cat-file', '-e', f'{commit}^{{commit}}'], cwd=ROOT,
                              capture_output=True).returncode == 0
    except OSError:
        return False


def pinned_paths(commit: str, paths: list[str]) -> dict[str, bool]:
    out = subprocess.run(['git', 'ls-tree', '-r', '--name-only', commit, '--', *paths], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    present = set(out)
    return {p: p in present for p in paths}


# --- Manifest -------------------------------------------------------------------------------

def strref_status(value: str, tlk_ids: set[int]) -> dict:
    if value in ('****', ''):
        return {'value': None, 'source': 'none'}
    ref = int(value)
    if ref >= TLK_CUSTOM_BASE:
        entry = ref - TLK_CUSTOM_BASE
        return {'value': ref, 'source': 'srn.tlk', 'entry': entry, 'resolved': entry in tlk_ids}
    return {'value': ref, 'source': 'base-game dialog.tlk', 'resolved': 'not checked (installed game)'}


def blueprint_record(path: Path, data: bytes, rows: dict, tlk_ids: set[int]) -> dict:
    gff = parse_gff(data)
    base = gff.get('BaseItem')
    row = rows.get(base, {})
    model_type = row.get('ModelType')
    parts = {k: gff[k] for k in ('ModelPart1', 'ModelPart2', 'ModelPart3') if k in gff}
    lo, hi = (int(row[k]) if row.get(k, '****') != '****' else None for k in ('MinRange', 'MaxRange'))
    used = sorted(set(parts.values())) if model_type != '0' else [parts.get('ModelPart1', 0)]
    name = gff.get('LocalizedName', {'strRef': NO_STRREF, 'strings': {}})
    desc = gff.get('Description', {'strRef': NO_STRREF, 'strings': {}})
    return {
        'path': rel(path),
        'resRef': path.stem,
        'sha256': sha256(data),
        'bytes': len(data),
        'pack': WEAPON_PACK,
        'tag': gff.get('Tag'),
        'templateResRef': gff.get('TemplateResRef'),
        'baseItem': base,
        'baseItemLabel': row.get('label'),
        'modelType': model_type,
        'modelParts': parts,
        'modelNumbersInRange': all(lo is not None and hi is not None and lo <= n <= hi for n in used),
        'baseItemRange': [lo, hi],
        'localizedName': {'strRef': None if name['strRef'] == NO_STRREF else name['strRef'],
                          'embedded': name['strings']},
        'description': {'strRef': None if desc['strRef'] == NO_STRREF else desc['strRef'],
                        'embedded': desc['strings']},
        'tlkDependency': 'none (embedded locstrings)' if name['strRef'] == NO_STRREF and desc['strRef'] == NO_STRREF
        else 'requires TLK',
        'cost': gff.get('Cost'),
        'stackSize': gff.get('StackSize'),
        'propertyCount': len(gff.get('PropertiesList', [])),
        'plot': gff.get('Plot'),
        'cursed': gff.get('Cursed'),
    }


def expected_resources(bp: dict) -> list[str]:
    out = []
    cls = (bp['itemClass'] or '').lower()
    if bp['modelType'] == '2':
        for part, letter in (('ModelPart1', 'b'), ('ModelPart2', 'm'), ('ModelPart3', 't')):
            n = bp['modelParts'].get(part)
            if n is not None:
                out += [f'{cls}_{letter}_{n:03d}.mdl', f'i{cls}_{letter}_{n:03d}.tga']
    elif bp['modelType'] == '0' and 'ModelPart1' in bp['modelParts']:
        name=f"{cls}_{bp['modelParts']['ModelPart1']:03d}"
        out += [name+'.mdl','i'+name+'.tga']
    return out


def list_weapon_files() -> list[Path]:
    return sorted(p for p in (ROOT / WEAPON_PACK).iterdir() if p.is_file())


def tracked_pack_files(pack_names: list[str]) -> dict[str, list[str]]:
    # The git index lists every tracked pack file even in a sparse checkout; walk folders only without git.
    try:
        out = subprocess.run(['git', 'ls-files', '-z', '--', *pack_names], cwd=ROOT, capture_output=True,
                             check=True).stdout.decode('utf-8')
    except (OSError, subprocess.CalledProcessError):
        return {n: sorted(f.name for f in (ROOT / n).iterdir() if f.is_file())
                for n in pack_names if (ROOT / n).is_dir()}
    files: dict[str, list[str]] = {}
    for path in filter(None, out.split('\0')):
        pack, _, name = path.partition('/')
        if pack in pack_names and name and '/' not in name:
            files.setdefault(pack, []).append(name)
    return files


def build(check_git: bool = True) -> dict:
    publication = load_json(PUBLICATION)
    validation_sha = sha256(read(VALIDATION))
    columns, rows = parse_2da(read(BASEITEMS).decode('cp1252'))
    tlk = load_json(TLK)
    tlk_ids = {e['id'] for e in tlk['entries']}
    allocations = load_json(ALLOCATIONS)
    hak = load_json(HAKBUILDER)
    pack_names = [h['Name'] for h in hak['HakList']]

    weapon_files = list_weapon_files()
    pub_by_path = {r['path']: r for r in publication['resources']}
    item_by_blueprint = {bp: item for item in publication['items'] for bp in item['blueprints']}
    published_weapon = {r['path'].split('/', 1)[1]: r for r in publication['resources']
                        if r['path'].startswith(WEAPON_PACK + '/')}
    # Published maps count as candidates even when absent, so a deleted texture stays a missing dependency.
    texture_names = {Path(n).stem.lower() for n in [p.name for p in weapon_files] + list(published_weapon)
                     if Path(n).suffix.lower() in TEXTURE_SUFFIXES}

    # Resource inventory (with publication hash comparison).
    resources = []
    for p in weapon_files:
        rp = Path(WEAPON_PACK) / p.name
        data = p.read_bytes()
        pub = pub_by_path.get(rel(rp))
        entry = {
            'path': rel(rp), 'resRef': p.stem, 'type': p.suffix.lower().lstrip('.'),
            'resourceType': RESOURCE_TYPES.get(p.suffix.lower()), 'bytes': len(data),
            'sha256': sha256(data), 'pack': WEAPON_PACK,
            'item': pub['item'] if pub else None,
            'publicationSha256Match': bool(pub and pub['sha256'] == sha256(data)),
            'sourceArchive': pub.get('sourceArchive') if pub else None,
        }
        if p.suffix.lower() == '.mdl':
            strings = model_strings(data)
            entry['textureRefs'] = sorted(strings & texture_names)
            entry['invisiblePart'] = not entry['textureRefs']
        resources.append(entry)
    by_name = {r['path'].split('/', 1)[1].lower(): r for r in resources}

    # Blueprints and item closure.
    items = []
    for item in publication['items']:
        bps = []
        for resref in item['blueprints']:
            path = Path(WEAPON_PACK) / f'{resref}.uti'
            bp = blueprint_record(path, read(path), rows, tlk_ids)
            bp['itemClass'] = rows.get(bp['baseItem'], {}).get('ItemClass')
            bps.append(bp)
        closure, missing = set(), []
        closure.update(item.get('compatibilityResources', []))
        closure.update(item.get('projectileResources', []))
        for bp in bps:
            closure.add(Path(bp['path']).name)
            for name in expected_resources(bp):
                if name in by_name:
                    closure.add(name)
                    for tex in by_name[name].get('textureRefs', []):
                        closure.add(f'{tex}.tga')
                else:
                    missing.append(name)
        owned = {n for n, r in published_weapon.items() if r['item'] == item['id']}
        closure_missing = sorted(set(missing) | {n for n in closure | owned if n.lower() not in by_name})
        # Hidden placeholder parts (and their icons) fill unused multipart slots; see pistol-trial-checkpoint.md.
        placeholders = sorted(n for n in owned - closure
                              if (n.endswith('.mdl') and by_name.get(n.lower(), {}).get('invisiblePart'))
                              or (n.startswith('i') and by_name.get(n[1:-4].lower() + '.mdl', {}).get('invisiblePart')))
        base_rows = sorted({bp['baseItem'] for bp in bps})
        changed_rows={publication['displayTable']['baseItem']}|{r['baseItem'] for r in publication.get('additionalDisplayRows',[])}
        table_required=bool(set(base_rows)&changed_rows)
        items.append({
            'id': item['id'], 'name': item['name'], 'status': item['status'],
            'family': item.get('family'),
            'sourceArchive': item['sourceArchive'],
            'slingRelevant': SLING_ROW in base_rows,
            'baseItemRows': base_rows,
            'blueprints': bps,
            'resourceClosure': sorted(closure),
            'closureMissing': closure_missing,
            'contractPlaceholders': placeholders,
            'closureMatchesPublicationOwnership': sorted(closure | set(placeholders)) == sorted(owned),
            'tlkStrings': 'none required; names are embedded CExoLocStrings' if all(bp['tlkDependency'].startswith('none') for bp in bps)
                          else 'required by ' + ', '.join(bp['resRef'] for bp in bps if not bp['tlkDependency'].startswith('none')),
            'tables': [{'resource': rel(BASEITEMS), 'pack': TABLE_PACK, 'rows': base_rows}],
            'packs': sorted({WEAPON_PACK, TABLE_PACK} if table_required else {WEAPON_PACK}),
            'stockTableDependency': None if table_required else
            'Uses the shipped baseitems.2da row; srn_2da carries it unchanged',
        })

    # baseitems rows that the slice depends on.
    bullet_rows = [i for i, r in rows.items() if r.get('label', '').lower() in ('bullet', 'bullets')]
    referenced = sorted({r for it in items for r in it['baseItemRows']} | set(bullet_rows))
    table_rows = []
    for idx in referenced:
        row = rows[idx]
        rec = {'row': idx, **{c: row.get(c) for c in BASEITEM_COLUMNS if c in columns}}
        rec['strRefs'] = {c: strref_status(row.get(c, '****'), tlk_ids) for c in BASEITEM_STRREF_COLUMNS if c in columns}
        changes={r['baseItem']:r['changes'] for r in publication.get('additionalDisplayRows',[])}
        changes[publication['displayTable']['baseItem']]=publication['displayTable']['changes']
        rec['modifiedFromInstalledGame'] = idx in changes
        if rec['modifiedFromInstalledGame']:
            rec['changes'] = changes[idx]
        rec['role'] = ('sling family (Colt L36 host row)' if idx == SLING_ROW else
                       'sling ammunition (bullets)' if idx in bullet_rows else 'weapon family host row')
        table_rows.append(rec)
    baseitems_sha = sha256(read(BASEITEMS))

    # Resref collisions: across registered packs, and against staged MDRNEE item content.
    pack_files: dict[str, list[str]] = {}
    for name, files in tracked_pack_files(pack_names).items():
        for f in files:
            pack_files.setdefault(f.lower(), []).append(name)
    weapon_names = {r['path'].split('/', 1)[1].lower() for r in resources}
    pack_collisions = sorted(
        ({'resource': n, 'packs': sorted(pack_files[n])} for n in weapon_names | {'baseitems.2da'}
         if len(pack_files.get(n, [])) > 1), key=lambda c: c['resource'])
    mdrnee = load_json(MDRNEE_ITEMS)
    mdrnee_names = {r['name'].lower(): r for r in mdrnee['resources']}
    staged_collisions = sorted(
        ({'resource': n, 'mdrneeSha256': mdrnee_names[n]['sha256'],
          'mdrneeDisposition': mdrnee_names[n]['disposition'],
          'mdrneeRecommendedPack': mdrnee_names[n]['recommendedPack'],
          'identicalBytes': mdrnee_names[n]['sha256'] == by_name[n]['sha256']}
         for n in weapon_names if n in mdrnee_names), key=lambda c: c['resource'])
    sling_family_staged = sorted(n for n in mdrnee_names if re.match(r'i?wbwsl_[bmt]_\d{3}\.(mdl|tga|dds)$', n))
    migration = load_json(MDRNEE_MIGRATION)
    legacy_row61 = sorted(b['resref'] for b in migration['blueprints'] if b['baseItem'] == SLING_ROW)

    # Pinned-commit comparison.
    tracked = [r['path'] for r in resources] + [rel(BASEITEMS), rel(TLK), rel(ALLOCATIONS), rel(PUBLICATION)]
    pinned = None
    if check_git and git_available(PINNED_COMMIT):
        presence = pinned_paths(PINNED_COMMIT, tracked)
        tlk_pinned = json.loads(subprocess.run(['git', 'show', f'{PINNED_COMMIT}:{rel(ALLOCATIONS)}'], cwd=ROOT,
                                               capture_output=True, text=True, check=True).stdout)
        pinned_packs = json.loads(subprocess.run(['git', 'show', f'{PINNED_COMMIT}:{rel(HAKBUILDER)}'], cwd=ROOT,
                                                 capture_output=True, text=True, check=True).stdout)
        pinned = {
            'commit': PINNED_COMMIT,
            'weaponPackRegistered': WEAPON_PACK in [h['Name'] for h in pinned_packs['HakList']],
            'tablePackRegistered': TABLE_PACK in [h['Name'] for h in pinned_packs['HakList']],
            'presentPaths': sorted(p for p, ok in presence.items() if ok),
            'absentPaths': sorted(p for p, ok in presence.items() if not ok),
            'tlkNextId': tlk_pinned['nextId'],
        }

    sr_nwn_keys = sorted(a['key'] for a in allocations['allocations'] if a['owner'] == 'SR_NWN')
    combat_keys = sorted(a['key'] for a in allocations['allocations'] if a['key'].startswith('combat.'))

    gaps = [
        {'id': 'pinned-commit-lacks-weapons', 'severity': 'blocking-for-consumer',
         'text': 'None of the srn_weapon resources, srn_2da/baseitems.2da or the publication manifest exist at '
                 'the SR_NWN-pinned commit; SR_NWN must advance its SRN_HAKS submodule to consume this slice.'},
        {'id': 'sling-row61-global-display-change', 'severity': 'integration-decision',
         'text': 'srn_2da/baseitems.2da changes Sling row 61 ModelType 0->2 and MaxRange 50->'
                 f"{publication['displayTable']['changes']['MaxRange']['after']} for the whole "
                 'Sling family. Ordinary/stock simple-model slings are not client-qualified under this table.'},
        {'id': 'baseitems-full-table-override', 'severity': 'integration-decision',
         'text': 'srn_2da ships a complete baseitems.2da. Any SR_NWN or other HAK baseitems change requires an '
                 'intentional row-level merge; load order is not a substitute.'},
        {'id': 'no-firearm-mechanics', 'severity': 'scope',
         'text': 'Colt L36 retains Sling gameplay (damage, range, feats, ammunition). No firearm rules, ammunition '
                 'items, projectile models or ammunition tables are published; sling projectiles fall back to the '
                 'installed game.'},
        {'id': 'no-ammunition-assets', 'severity': 'gap-for-sling-target',
         'text': 'No sling bullet blueprint, ammunition model/icon, projectile model or ammunitiontypes.2da override '
                 'exists in any SRN_HAKS pack. The bullets row is carried unchanged.'},
        {'id': 'unpriced-blueprints', 'severity': 'gap-for-combat',
         'text': 'Published blueprints retain their reviewed costs and item properties; they are builder templates without '
                 'balance data. Combat stats come only from the base item row.'},
        {'id': 'no-combat-tlk', 'severity': 'info',
         'text': f'No combat.* TLK allocations exist (SR_NWN-owned keys: {len(sr_nwn_keys)}, all phenomorpher race '
                 'strings). The weapon blueprints need no TLK entries; any combat UI/feedback strings SR_NWN needs '
                 'must be allocated with tools/Allocate-StrRef.ps1.'},
        {'id': 'rights-reference-origin', 'severity': 'rights-review',
         'text': 'PROVENANCE.md records operator-supplied references and Pixal3D generation but not the origin/'
                 'license of the reference images or the generator terms for redistributed outputs.'},
        {'id': 'rights-trademarks', 'severity': 'rights-review',
         'text': 'The Colt L36 and Cougar names/branding are third-party marks; PROVENANCE.md explicitly does not '
                 'assert ownership. GOVERNANCE.md requires trademark review per batch; no recorded clearance.'},
        {'id': 'client-qualification-scope', 'severity': 'qualification',
         'text': 'User acceptance covers the shipped Human fixture only; individual animation, armor, glove and '
                 'off-hand cases and other bodies (c7 lock) were not separately client-tested.'},
        {'id': 'base-game-collision-unchecked', 'severity': 'verify',
         'text': 'Weapon resrefs were not compared against an installed NWN:EE key/bif set in this run.'},
    ]
    if staged_collisions:
        gaps.append({'id': 'mdrnee-staged-resref-collision', 'severity': 'id-collision',
                     'text': f'{len(staged_collisions)} srn_weapon resrefs also exist with different bytes in the '
                             'staged (quarantined) MDRNEE item HAK; a future MDRNEE promotion must renumber or drop them.'})
    if legacy_row61:
        gaps.append({'id': 'mdrnee-legacy-row61', 'severity': 'id-collision',
                     'text': f'{len(legacy_row61)} staged MDRNEE blueprints use legacy BaseItem 61 as a dual-wield '
                             'handgun; in the EE baseline row 61 is the Sling hosting the Colt L36.'})
    if pack_collisions:
        gaps.append({'id': 'pack-resref-collision', 'severity': 'id-collision',
                     'text': 'Weapon resrefs duplicated across registered packs: '
                             + ', '.join(c['resource'] for c in pack_collisions)})
    for it in items:
        for bp in it['blueprints']:
            if not bp['modelNumbersInRange']:
                lo, hi = bp['baseItemRange']
                gaps.append({'id': f"model-range-{bp['resRef']}", 'severity': 'verify',
                             'text': f"{bp['resRef']} uses model parts {sorted(set(bp['modelParts'].values()))} outside "
                                     f"baseitems row {bp['baseItem']} MinRange/MaxRange {lo}-{hi}. The toolset part "
                                     'picker cannot select it; the shipped blueprint was client-reviewed as-is. '
                                     'SR_NWN-authored variants must copy the blueprint rather than re-pick parts, '
                                     'or a reviewed MaxRange merge is needed.'})
        if it['closureMissing']:
            gaps.append({'id': f"closure-missing-{it['id']}", 'severity': 'blocking',
                         'text': 'Missing closure resources: ' + ', '.join(it['closureMissing'])})
    for r in resources:
        if not r['publicationSha256Match']:
            gaps.append({'id': f"hash-drift-{r['resRef']}", 'severity': 'blocking',
                         'text': f"{r['path']} does not match approved-weapons-v1.json"})

    return {
        'schemaVersion': 1,
        'kind': 'srn-release-manifest',
        'slice': 'sr-nwn-phase-2a-combat-weapons',
        'status': 'inventory-only',
        'statusNote': 'Describes tracked content and its dependency closure. Grants no asset, rights, client, '
                      'production or SR_NWN integration approval and performs no SR_NWN->SRN_NWN export.',
        'consumer': {'repository': 'SR_NWN (private)', 'pinnedSrnHaksCommit': PINNED_COMMIT,
                     'projectileTarget': 'sling (SR_NWN decisions D376-D378)'},
        'authorities': {
            rel(PUBLICATION): sha256(read(PUBLICATION)),
            rel(VALIDATION): validation_sha,
            rel(FIREARM_GRIP): sha256(read(FIREARM_GRIP)),
            rel(BLADE_GRIP): sha256(read(BLADE_GRIP)),
            'PROVENANCE.md#approved-cougar-blades-and-colt-l36': 'section record (srn_weapon, 2026-10-24)',
        },
        'loadContract': {
            'packs': [WEAPON_PACK, TABLE_PACK],
            'registeredInHakbuilder': {p: p in pack_names for p in (WEAPON_PACK, TABLE_PACK)},
            'buildCommand': "./tools/Build-Haks.ps1 -Pack @('srn_weapon', 'srn_2da') -SkipTlk",
            'tlkRequired': False,
            'note': 'Load srn_weapon with srn_2da for F7 multipart carriers and F2 appearance addresses. '
                    'Production body/firing overlays are excluded; animations belong to PhenoMorpher toolkit. HAK archives are '
                    'ignored build outputs and are not hashed here; resource hashes are the release identity.',
        },
        'items': items,
        'resources': resources,
        'tables': [{'resource': rel(BASEITEMS), 'pack': TABLE_PACK, 'sha256': baseitems_sha,
                    'matchesPublicationOverride': baseitems_sha == publication['displayTable']['overrideSha256'],
                    'installedGameOriginalSha256': publication['displayTable']['originalSha256'],
                    'rows': table_rows}],
        'tlk': {'resource': rel(TLK), 'sha256': sha256(read(TLK)), 'allocationsSha256': sha256(read(ALLOCATIONS)),
                'nextId': allocations['nextId'],
                'weaponEntries': sorted({ref['entry'] for row in table_rows for ref in row['strRefs'].values() if ref['source'] == 'srn.tlk'}),
                'combatKeys': combat_keys,
                'srNwnOwnedKeys': sr_nwn_keys},
        'rights': {
            'record': 'PROVENANCE.md "Approved Cougar blades and Colt L36 (srn_weapon, 2026-10-24)"',
            'origin': 'Operator-supplied references; Pixal3D geometry/appearance; local fit, UV, texture transfer, '
                      'NWN:EE compile. baseitems.2da is an installed-game compatibility derivative.',
            'approvalEvidence': publication['approvalEvidence'],
            'productionDeploymentPerformed': publication['productionDeploymentPerformed'],
            'openItems': ['rights-reference-origin', 'rights-trademarks'],
        },
        'collisions': {'registeredPacks': pack_collisions, 'stagedMdrneeItemHak': staged_collisions,
                       'stagedMdrneeSlingFamilyResources': len(sling_family_staged),
                       'stagedMdrneeLegacyRow61Blueprints': legacy_row61},
        'excluded': {'production-weapon-motion-overlays': 'itemkit testing only; production animation belongs to PhenoMorpher toolkit',
                     'mdrnee-weapons': f"{migration['status']}; not runtime-ready, not in any pack"},
        'pinnedComparison': pinned,
        'gaps': gaps,
    }


def render_md(m: dict) -> str:
    L = ['# SR_NWN Phase 2A combat slice: weapon release manifest', '',
         '<!-- Generated by tools/combat_release_manifest.py; edit the generator, not this file. -->', '',
         f"Machine-readable manifest: `{rel(JSON_OUT)}` (status **{m['status']}**). {m['statusNote']}", '',
         f"Consumer: {m['consumer']['repository']}, pinned SRN_HAKS `{PINNED_COMMIT[:7]}`. "
         f"Projectile target: {m['consumer']['projectileTarget']}.", '',
         '## Load contract', '',
         f"Packs: `{'`, `'.join(m['loadContract']['packs'])}` (TLK not required). Build only these with "
         f"`{m['loadContract']['buildCommand']}`. {m['loadContract']['note']}", '',
         '## Items', '',
         '| Item | Status | Blueprint(s) | Base row | Model parts | Sling | Packs |', '|---|---|---|---|---|---|---|']
    for it in m['items']:
        bps = ', '.join(f"`{b['resRef']}`" for b in it['blueprints'])
        parts = '; '.join('/'.join(str(v) for v in b['modelParts'].values()) for b in it['blueprints'])
        rows = ', '.join(f"{b['baseItem']} {b['baseItemLabel']}" for b in it['blueprints'][:1])
        L.append(f"| {it['name']} | {it['status']} | {bps} | {rows} | {parts} | "
                 f"{'**yes**' if it['slingRelevant'] else 'no'} | {', '.join(it['packs'])} |")
    blueprints = [b for it in m['items'] for b in it['blueprints']]
    exceptions = sorted(b['resRef'] for b in blueprints if not b['tlkDependency'].startswith('none') or b['cost'] or b['propertyCount'])
    L += ['', ('All blueprints carry embedded names (no TLK StrRef), Cost 0 and no item properties. ' if not exceptions else
               'Blueprints with a TLK StrRef, a Cost or item properties: ' + ', '.join(f'`{r}`' for r in exceptions) + '. ') +
          'Model numbers outside their base row MinRange/MaxRange: '
          + (', '.join(f"`{b['resRef']}`" for it in m['items'] for b in it['blueprints'] if not b['modelNumbersInRange'])
             or 'none') + ' (see Gaps).', '',
          'Each item closure (blueprint, part models, icons, diffuse maps) matches the publication ownership: '
          + ('yes' if all(it['closureMatchesPublicationOwnership'] for it in m['items']) else '**no**') + '. '
          + ' '.join(f"{it['name']} also ships unreferenced hidden-slot placeholders "
                     f"({', '.join('`' + p + '`' for p in it['contractPlaceholders'])}) so every multipart "
                     'slot resolves; each blueprint names its own bottom-part address.' for it in m['items'] if it['contractPlaceholders']),
          '',
          '## Resources', '', '| Path | Item | Bytes | SHA-256 | Textures | Pub. match |', '|---|---|---:|---|---|---|']
    for r in m['resources']:
        tex = ', '.join(r.get('textureRefs', [])) or ('(invisible part)' if r.get('invisiblePart') else '')
        L.append(f"| `{r['path']}` | {r['item']} | {r['bytes']} | `{r['sha256']}` | {tex} | "
                 f"{'yes' if r['publicationSha256Match'] else '**NO**'} |")
    t = m['tables'][0]
    L += ['', '## Tables', '',
          f"`{t['resource']}` ({t['pack']}) SHA-256 `{t['sha256']}`; matches the reviewed override: "
          f"{'yes' if t['matchesPublicationOverride'] else '**no**'}.", '',
          '| Row | Label | Role | ModelType | ItemClass | Range | WeaponType | Ranged | Ammo | Dice | Name StrRef | Modified |',
          '|---:|---|---|---|---|---|---|---|---|---|---|---|']
    for r in t['rows']:
        name = r['strRefs'].get('Name', {})
        mod = ', '.join(f"{k} {v['before']}->{v['after']}" for k, v in r.get('changes', {}).items()) or 'no'
        L.append(f"| {r['row']} | {r['label']} | {r['role']} | {r['ModelType']} | {r['ItemClass']} | "
                 f"{r['MinRange']}-{r['MaxRange']} | {r['WeaponType']} | {r['RangedWeapon']} | "
                 f"{r.get('AmmunitionType')} | {r['NumDice']}d{r['DieToRoll']} | {name.get('value')} ({name.get('source')}) | {mod} |")
    tl = m['tlk']
    L += ['', '## TLK', '',
          f"`{tl['resource']}` SHA-256 `{tl['sha256']}`, nextId {tl['nextId']}. Weapon entries: {', '.join(map(str, tl['weaponEntries'])) or 'none'}. "
          f"`combat.*` keys: {len(tl['combatKeys'])}. "
          + ('Other base-row StrRefs resolve' if tl['weaponEntries'] else 'All base-row StrRefs resolve') + ' to the base-game dialog.tlk.', '',
          '## Pinned commit vs HEAD', '']
    p = m['pinnedComparison']
    if p:
        L.append(f"At `{p['commit'][:7]}`: `srn_weapon` registered: {p['weaponPackRegistered']}; `srn_2da` registered: "
                 f"{p['tablePackRegistered']}; TLK nextId {p['tlkNextId']}. Present there: "
                 + (', '.join(f'`{x}`' for x in p['presentPaths']) or 'none') + f". Absent there: {len(p['absentPaths'])} "
                 "of the slice's paths (every weapon resource, `baseitems.2da` and the publication manifest). "
                 "The weapon slice exists only after the pinned commit (added in #57).")
    else:
        L.append('Pinned commit not available in this checkout; comparison not regenerated.')
    c = m['collisions']
    L += ['', '## Collisions', '',
          f"Across registered packs: {len(c['registeredPacks'])}. Staged MDRNEE item HAK resrefs shared with "
          f"`srn_weapon`: {len(c['stagedMdrneeItemHak'])} "
          f"({', '.join('`' + x['resource'] + '`' for x in c['stagedMdrneeItemHak'])}); none byte-identical: "
          f"{not any(x['identicalBytes'] for x in c['stagedMdrneeItemHak'])}. Staged MDRNEE multipart sling resources: "
          f"{c['stagedMdrneeSlingFamilyResources']}. Staged MDRNEE blueprints on legacy row 61: "
          f"{len(c['stagedMdrneeLegacyRow61Blueprints'])}.", '',
          '## Rights and provenance', '', f"Record: {m['rights']['record']}. {m['rights']['origin']} "
          f"Production deployment performed: {m['rights']['productionDeploymentPerformed']}.", '',
          '## Gaps', '', '| Id | Severity | Detail |', '|---|---|---|']
    L += [f"| `{g['id']}` | {g['severity']} | {g['text']} |" for g in m['gaps']]
    L += ['', '## Excluded', '']
    L += [f"- `{k}`: {v}" for k, v in m['excluded'].items()]
    return '\n'.join(L) + '\n'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='Fail if the tracked manifest is stale')
    args = ap.parse_args(argv)
    manifest = build()
    if manifest['pinnedComparison'] is None and (ROOT / JSON_OUT).exists():
        manifest['pinnedComparison'] = load_json(JSON_OUT).get('pinnedComparison')
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'
    md = render_md(manifest)
    if args.check:
        stale = [p for p, body in ((JSON_OUT, text), (MD_OUT, md))
                 if not (ROOT / p).exists() or (ROOT / p).read_text(encoding='utf-8') != body]
        if stale:
            print('stale: ' + ', '.join(rel(p) for p in stale), file=sys.stderr)
            return 1
        print('combat release manifest is current')
        return 0
    (ROOT / JSON_OUT).write_text(text, encoding='utf-8', newline='\n')
    (ROOT / MD_OUT).write_text(md, encoding='utf-8', newline='\n')
    print(f'wrote {rel(JSON_OUT)} and {rel(MD_OUT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
