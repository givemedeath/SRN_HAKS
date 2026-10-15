"""Read-only check sweep over published bodies (promoted from the runtime-optimization Phase 6 script).

Per body: native attributes, assembled measurements, geometry audit, standing connector audits on the
body itself and against the same-gender Human donor of the same build, and optionally a motion
connector sweep over the body's own effective clips. Connector surfaces use v16: neck links and
penetration on closed oriented (also non-manifold) parts. Writes one JSON file per body; no approvals.
"""
import hashlib
import json
import re
from pathlib import Path

import numpy as np

from .. import api
from . import anim_library as lib
from . import check_connector_surfaces_v16 as surfaces
from . import check_terminal_connectivity_v13c as terminal
from . import silhouette_model as sil
from . import nwn_part_measurements as parts_measure
from .check_terminal_connectivity_v13 import LINKS
from .fit_scale_position_v13a import terminal_inventory, terminal_contact
from .morph_preview_pose_v13 import pose_rigid_meshes
from .native_motion import sample, sample_times

KIND = 'PhenoMorpher-body-sweep'
CORE = ['pause1', 'pause2', 'walk', 'run', 'nwkickl', 'nwkickr']
GATE = ['walk_swordr', 'run_swordl', 'tlknorm', 'salute', 'greeting', 'torchl']
PART = re.compile(r'p[fm][a-z][0-9]_([a-z]+)001\.mdl')


def canonical(name):
    return re.sub(r'^p[fm][a-z][0-9]_', '', name)


def donor_of(prefix):
    return f'p{prefix[1]}h{prefix[3]}'


def body_files(root, contract, prefix):
    """Rig, parts and (when the pack publishes it) the head001 routing alias for one target."""
    target = next(t for t in contract['targets'] if t['modelPrefix'] == prefix)
    pack = {r['path'] for r in contract['resources']}
    parts = {PART.match(n)[1]: root/'srn_body'/n for n in target['parts']}
    head = f'srn_body/{prefix}_head001.mdl'
    if head in pack:
        parts['head'] = root/head
    return root/'srn_body'/(prefix + '.mdl'), parts


def consumed(root, contract, prefixes):
    """Every pack file a sweep over these prefixes and their donors reads."""
    files = set()
    for prefix in set(prefixes) | {donor_of(p) for p in prefixes}:
        rig, parts = body_files(root, contract, prefix); files.add(rig); files.update(parts.values())
    return files


def body(root, contract, prefix):
    rig, parts = body_files(root, contract, prefix)
    meshes, joints = sil.assemble(rig, parts)
    meshes = [{**m, 'name': canonical(m['name'])} for m in meshes]
    return {'prefix': prefix, 'rig': rig, 'parts': parts, 'meshes': meshes, 'joints': joints, 'frames': sil.frames(sil.decode(rig)[0])}


def native_info(b):
    rows = {}
    for path in [b['rig'], *b['parts'].values()]:
        skeleton, attributes, _ = api.read_attributes(path)
        rows[path.name] = {'nodes': len(skeleton), 'meshes': {n: {'vertices': len(r['position']), 'triangles': len(r['faces']),
                           'attributes': [k for k in ('normal', 'uv', 'tangent', 'sign', 'color') if k in r]} for n, r in attributes.items()}}
    return rows


def geometry_audit(meshes):
    degenerate = {}; keys = {}
    for m in meshes:
        if not m.get('render', True):
            continue
        p = np.asarray(m['position']); f = np.asarray(m['faces'])
        tri = p[f]; area = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)
        degenerate[m['part']+'/'+m['name']] = int((area < 1e-12).sum())
        for row in np.round(tri, 6):
            keys.setdefault(tuple(sorted(map(tuple, row))), set()).add(m['part'])
    return {'degenerateTriangles': {k: v for k, v in degenerate.items() if v},
            'coincidentCrossPartTriangles': sum(1 for parts in keys.values() if len(parts) > 1)}


def measurements(b):
    meshes = [m for m in b['meshes'] if m['part'] != 'head']
    report = sil.measure(meshes, b['joints']); sections = parts_measure.model_parts(meshes, b['joints'])
    masks = {v: hashlib.sha256(np.packbits(sil.rasterize(meshes, v)[0]).tobytes()).hexdigest() for v in ('front', 'left', 'back', 'right')}
    return {'stature': report.get('bindStatureMeters'), 'segments': report.get('jointSegmentMeters'), 'sections': sections, 'maskSHA256': masks}


def aligned(source, candidate):
    """Mesh pairs with identical lineage for the minimum audit; others are dropped from both and reported."""
    s_index = {(m['part'], m['name']): m for m in source}; keep_s = []; keep_c = []; dropped = []
    for m in candidate:
        other = s_index.get((m['part'], m['name']))
        if other is not None and other.get('render', True) == m.get('render', True) and np.asarray(other['position']).shape == np.asarray(m['position']).shape \
                and np.array_equal(other['faces'], m['faces']):
            keep_s.append(other); keep_c.append(m)
        else:
            dropped.append(m['part']+'/'+m['name'])
    return keep_s, keep_c, dropped


def connectors(source, candidate, scales):
    s, c, dropped = aligned(source['meshes'], candidate['meshes'])
    minimum = terminal.audit_minimum(s, c, source['frames'], candidate['frames'], scales)
    # v16 checks lineage per link, so a donor topology difference drops only that link.
    area = surfaces.audit(source['meshes'], candidate['meshes'], source['frames'], candidate['frames'], scales)
    return {'droppedForLineage': dropped, 'minimum': minimum, 'surfaces': area}


def posed_frames(models, prefix, clip_name, time):
    names = lib.chain(prefix, models); owner = lib.effective(names, models)[clip_name]['owner']; clip = models[owner]['clips'][clip_name]
    animated = {(prefix if n == owner else n): row for n, row in clip['nodes'].items()}
    return sample(models[prefix]['nodes'], animated, time), clip, owner


def motion(models, b, donor, clips):
    prefix = b['prefix']; rows = {}
    bind = sample(models[prefix]['nodes'], {}, 0.)
    drift = max(float(np.abs(np.asarray(bind[j])-np.asarray(b['frames'][j])).max()) for j in b['frames'] if j in bind)
    inventories = {}
    for left, right in LINKS:
        try:
            inventories[(left, right)] = (terminal_inventory(b['meshes'], b['frames'], left, right),
                                          terminal_inventory(donor['meshes'], donor['frames'], left, right))
        except ValueError as error:
            rows[f'{left}-{right}'] = {'status': 'unavailable', 'reason': str(error)}
    feet = lambda meshes: min(float(np.asarray(m['position'])[:, 2].min()) for m in meshes if m['part'] in ('footl', 'footr') and m.get('render', True))
    floor = feet(b['meshes']); donor_floor = feet(donor['meshes']); clip_rows = {}; missing = {}
    for clip_name in clips:
        try:
            _, clip, owner = posed_frames(models, prefix, clip_name, 0.)
        except KeyError:
            missing[clip_name] = 'absent from the target chain'; continue
        try:
            _, donor_clip, donor_owner = posed_frames(models, donor['prefix'], clip_name, 0.)
        except KeyError:
            missing[clip_name] = 'absent from the donor chain'; continue
        worst = {}; sole = []
        for t in sample_times(clip):
            fraction = t/clip['length'] if clip['length'] else 0.
            posed = posed_frames(models, prefix, clip_name, t)[0]
            donor_posed = posed_frames(models, donor['prefix'], clip_name, fraction*donor_clip['length'])[0]
            mesh_t = pose_rigid_meshes(b['meshes'], b['frames'], {**b['frames'], **posed})
            donor_t = pose_rigid_meshes(donor['meshes'], donor['frames'], {**donor['frames'], **donor_posed})
            sole.append((feet(mesh_t)-floor, feet(donor_t)-donor_floor, float(t)))
            for link, (inv, donor_inv) in inventories.items():
                ours = terminal_contact(mesh_t, inv); theirs = terminal_contact(donor_t, donor_inv)
                excess = ours['minimumTriangleClearanceMeters'] - theirs['minimumTriangleClearanceMeters']*b['scale']
                key = f'{link[0]}-{link[1]}'
                if key not in worst or excess > worst[key]['excessMeters']:
                    worst[key] = {'excessMeters': excess, 'clearanceMeters': ours['minimumTriangleClearanceMeters'],
                                  'donorClearanceMeters': theirs['minimumTriangleClearanceMeters'], 'time': float(t),
                                  'intersections': ours['intersectingTrianglePairCount'], 'donorIntersections': theirs['intersectingTrianglePairCount']}
        low = min(sole, key=lambda r: r[0])
        clip_rows[clip_name] = {'owner': owner, 'donorOwner': donor_owner, 'samples': len(sample_times(clip)), 'connectors': worst,
                                'lowestSoleBelowStandingMeters': low[0], 'donorLowestSoleBelowStandingMeters': min(r[1] for r in sole), 'lowestSoleTime': low[2]}
    return {'bindFrameAgreement': drift, 'unavailableLinks': rows, 'clips': clip_rows, 'unavailableClips': missing,
            'requestedClips': list(clips), 'scale': b['scale']}


def unresolved_clips(models, prefixes, clips):
    """Requested clips that some target or donor chain cannot resolve."""
    missing = []
    for prefix in sorted(set(prefixes) | {donor_of(p) for p in prefixes}):
        effective = lib.effective(lib.chain(prefix, models), models)
        missing += [f'{prefix}:{clip}' for clip in clips if clip not in effective]
    return missing


def sweep(root, manifest_path, output, prefixes, stock_manifest=None, with_motion=False, motion_only=False, clips=None, label=None):
    root = Path(root).resolve(); output = Path(output)
    contract = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    known = {t['modelPrefix'] for t in contract['targets']}
    if not prefixes or set(prefixes) - known:
        raise ValueError('Unknown sweep target: ' + ', '.join(sorted(set(prefixes) - known)))
    if with_motion and stock_manifest is None:
        raise ValueError('A motion sweep needs the extracted stock manifest')
    for path in consumed(root, contract, prefixes):
        rows = [r for r in contract['resources'] if root/r['path'] == path]
        if not rows or lib.digest(path.read_bytes()) != rows[0]['sha256']:
            raise ValueError('Published file differs from the contract: ' + str(path))
    models = None
    if with_motion:
        stock, stock_paths = lib.stock_files(stock_manifest); models, _ = lib.release_models(root, contract, stock, stock_paths)
        # Explicitly requested clips must all be measurable; the default set records gaps per body instead.
        if clips and (missing := unresolved_clips(models, prefixes, clips)):
            raise ValueError('Requested clip cannot be resolved: ' + ', '.join(missing))
    output.mkdir(parents=True, exist_ok=False); cache = {}; written = []
    def load(prefix):
        if prefix not in cache:
            cache[prefix] = body(root, contract, prefix)
        return cache[prefix]
    for prefix in prefixes:
        b = load(prefix); donor = load(donor_of(prefix))
        stature = sil.measure([m for m in b['meshes'] if m['part'] != 'head'], b['joints']).get('bindStatureMeters')
        donor_stature = sil.measure([m for m in donor['meshes'] if m['part'] != 'head'], donor['joints']).get('bindStatureMeters')
        b['scale'] = stature/donor_stature; scales = {p: b['scale'] for p in sil.PART_JOINTS}
        result = {'schemaVersion': 1, 'kind': KIND, 'release': label, 'contract': contract['version'],
                  'target': next(t['target'] for t in contract['targets'] if t['modelPrefix'] == prefix), 'prefix': prefix,
                  'donor': donor['prefix'], 'statureRatioToDonor': b['scale'], 'headIncluded': 'head' in b['parts']}
        if not motion_only:
            result.update({'nativeInfo': native_info(b), 'geometry': geometry_audit(b['meshes']), 'measurements': measurements(b),
                           'connectorsSelf': connectors(b, b, None),
                           'connectorsVsDonor': connectors(donor, b, scales) if prefix != donor['prefix'] else None})
        if with_motion:
            result['motion'] = motion(models, b, donor, clips or (CORE + GATE))
        result['assetApprovalCreated'] = False
        path = output/f'{prefix}.json'
        path.write_text(json.dumps(result, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)) + '\n',
                        encoding='utf-8', newline='\n')
        written.append(path.name)
    return {'kind': KIND, 'contract': contract['version'], 'bodies': written, 'motion': with_motion, 'assetApprovalCreated': False}
