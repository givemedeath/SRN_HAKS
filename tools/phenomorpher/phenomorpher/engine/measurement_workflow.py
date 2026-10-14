"""Measurement-only CLI: smoke, installed stock planning/extraction, and review.

Every execution is launched with launch_shared_tool.py. Output directories are
fresh/versioned; masks/ratios are proposals and confer no asset acceptance.
"""
import argparse
import html
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

from .measurement_common import pin, read, require, safe_relative, sha, verified, write
from .measurement_stock import extract, locate
from .silhouette_model import assemble, cross_section, measure as measure_model, rasterize
from .silhouette_reference import VIEWS, annotated_masks, foreground, measure, overlay, summarize
from .proportion_targets import transfer
from .target_contract import PART_JOINTS
from .pipeline import detect_view_spans


def smoke():
    image = Image.new('RGB', (40, 40), 'black')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 20, 35), fill=(170, 140, 110))
    draw.rectangle((0, 0, 20, 4), fill='cyan')
    mask = foreground(image)
    require(not mask[:5].any() and mask[10:36, 10:21].all(), 'Reference foreground smoke failed')
    box = np.array([[0, 0, 0], [.02, 0, 0], [0, 0, .02]])
    model_mask, _, _ = rasterize([{'part': 'chest', 'position': box, 'faces': np.array([[0, 1, 2]])}], 'front')
    require(model_mask.any() and transfer(1, 2, .5, .5, 2) == 1, 'Raster/ratio smoke failed')
    print(json.dumps({'kind': 'phenotype-measurement-python-smoke', 'checksPassed': True,
                      'executable': sys.executable, 'numpyVersion': np.__version__}))


def prepare_stock(root, output):
    require(not Path(output).exists(), 'Fresh stock input plan required')
    keys = sorted((Path(root) / 'data').rglob('*.key'))
    require(keys, 'Installed KEY files missing')
    for key in keys:
        verified(key, sha(key))
    prefixes = ('pmh0', 'pfh0', 'pmd0', 'pme0', 'pmo0', 'pmg0')
    names = [name for prefix in prefixes for name in [prefix + '.mdl',
             *(prefix + '_' + part + '001.mdl' for part in PART_JOINTS)]]
    resources = locate(root, keys, names)
    files = keys + sorted({Path(row['bif']) for rows in resources.values() for row in rows})
    write(output, {'kind': 'measurement-stock-input-plan', 'resources': resources,
                   'inputs': [pin(p) for p in files], 'gameClientTesting': False})
    print(json.dumps({'stockPlan': str(output), 'resources': len(resources), 'inputFiles': len(files)}))


def reference_batch(config, output, reference_root, evidence, pilot=False):
    lock_path = Path(config) / 'reference-sheets.lock.json'
    lock = read(lock_path)
    evidence.append(verified(lock_path, sha(lock_path)))
    policy_path = Path(config) / 'source-policy.json'
    evidence.append(verified(policy_path, sha(policy_path)))
    source_policy = read(policy_path)
    results = {}
    # The pilot is always first, regardless of lock insertion order.
    order = ['human_male_fit', 'dwarf_male_fit'] + [s for s in lock['sheets'] if s not in ('human_male_fit', 'dwarf_male_fit')]
    if pilot:
        order = order[:2]
    for slug in order:
        item = lock['sheets'][slug]
        path = safe_relative(reference_root, item['relativePath'])
        evidence.append(verified(path, item['sha256']))
        annotation_path = Path(config) / 'exclusions' / (slug + '.json')
        evidence.append(verified(annotation_path, sha(annotation_path)))
        annotation = read(annotation_path)
        require(annotation['sourceSha256'] == item['sha256'] and annotation['slug'] == slug,
                'Annotation/source identity changed')
        require(set(annotation['views']) == set(VIEWS), 'Four explicit view annotations required')
        image = Image.open(path).convert('RGB')
        require(image.size == (1916, 821), 'Unfamiliar reference dimensions')
        detected = detect_view_spans(image)
        packet = {}
        folder = Path(output) / 'reference' / slug
        folder.mkdir(parents=True)
        panels = Image.new('RGB', (1916, 760), '#20242b')
        preview_scale = min(479 / max(row['crop'][2] - row['crop'][0] for row in annotation['views'].values()), 760 / 821)
        for index, view in enumerate(VIEWS):
            row = annotation['views'][view]
            # Explicit crops must contain their detected figure span.
            require(row['crop'][0] <= detected[index][0] and row['crop'][2] >= detected[index][1],
                    'Annotation crop excludes detected view: ' + slug + '/' + view)
            full, body = annotated_masks(image, row)
            Image.fromarray(full.astype(np.uint8) * 255).save(folder / (view + '-full.png'))
            Image.fromarray(body.astype(np.uint8) * 255).save(folder / (view + '-body.png'))
            preview = overlay(image, row, body)
            preview.save(folder / (view + '-overlay.png'))
            preview = preview.resize((round(preview.width * preview_scale), round(preview.height * preview_scale)))
            panels.paste(preview, (index * 479 + (479 - preview.width) // 2, 0))
            packet[view] = measure(body, row)
        panels.save(folder / 'overlay.png')
        regenerated = Image.new('RGB', (image.width, image.height + 100), '#20242b')
        regenerated.paste(image, (0, 0))
        caption = ImageDraw.Draw(regenerated)
        caption.text((20, image.height + 10), slug + ' | Source-preserving measurement edition | source SHA-256 ' + item['sha256'], fill='white')
        caption.text((20, image.height + 35), 'No reconstructed anatomy. Exclusions/landmarks: overlay.png. Hair-obscured crown and clothing-covered anatomy remain provisional/unavailable.', fill='white')
        caption.text((20, image.height + 60), 'Lore context: shadowrunsixthworld.com/metatypes/ (Sixth World). Detailed dimensions use project calibration, not newly claimed canonical lore.', fill='white')
        regenerated.save(folder / 'source-sheet.png')
        result = {'slug': slug, 'source': pin(path), 'annotations': pin(annotation_path),
                  'sourcePolicy': pin(policy_path), 'loreStatus': source_policy['limits'],
                  'views': packet, **summarize(packet)}
        from .nwn_part_measurements import reference_parts
        result['nwnParts'] = reference_parts(result['measurements'])
        write(folder / 'measurements.json', result)
        results[slug] = result
    return results


def model_batch(config, output, references, evidence):
    results, assemblies = {}, {}
    for identity, entry in config['models'].items():
        paths = [entry['rig'], *entry['parts'].values()]
        for p in paths:
            evidence.append(verified(p, config['inputHashes'][str(Path(p).resolve())]))
        meshes, joints = assemble(entry['rig'], entry['parts'])
        result = measure_model(meshes, joints)
        result.update({'id': identity, 'role': entry['role'], 'reference': entry['reference'],
                       'inputs': [pin(p) for p in paths], 'referencePoseMatched': False,
                       'productionAcceptance': False})
        result['nativeMetadataDiscrepancies'] = [
            {'part': m['part'], 'mesh': m['name'], **m['nativeNodeCounts']}
            for m in meshes if 'nativeNodeCounts' in m and
            m['nativeNodeCounts']['declared'] != m['nativeNodeCounts']['reachable']]
        result['secondarySimulationMeasured'] = False
        result['stockSlotNote'] = entry.get('stockSlotNote')
        if set(entry['parts']) != set(PART_JOINTS):
            result['statureStatus'] = 'incomplete-body-not-full-stature'
        else:
            result['statureStatus'] = 'complete-bind-assembly-with-selected-stock-head'
        # Exact dimensions are sampled at reviewed reference landmark fractions;
        # their anatomical correspondence remains a proposal, not a claimed fit.
        dimensions = {}
        ref = references[entry['reference']]['measurements']
        height = result['bindStatureMeters']
        floor = result['boundsMeters'][0][2]
        for key, row in ref.items():
            if key.endswith('Height') or row['value'] is None:
                continue
            base = key.removesuffix('Width').removesuffix('Depth')
            landmark = ref.get(base + 'Height')
            if not landmark or landmark['value'] is None:
                continue
            if base in ('waist', 'chest', 'shoulder', 'hipClothedContour'):
                subset = [m for m in meshes if m['part'] in ('chest', 'pelvis')]
            elif base in ('midThigh', 'knee'):
                subset = [m for m in meshes if m['part'] in ('legl', 'legr', 'shinl', 'shinr')]
            elif base in ('calf', 'ankle'):
                subset = [m for m in meshes if m['part'] in ('shinl', 'shinr', 'footl', 'footr')]
            else:
                continue
            if key.endswith('Width') and base in ('midThigh', 'knee', 'calf', 'ankle'):
                halves = [[m for m in subset if m['part'].endswith(side)] for side in ('l', 'r')]
                values = [cross_section(group, floor + height * landmark['value'], 0) for group in halves]
                value = float(np.mean(values)) if all(v is not None for v in values) else None
            else:
                value = cross_section(subset, floor + height * landmark['value'], 0 if key.endswith('Width') else 1)
            dimensions[key] = value
        for key in ('upperArm', 'forearm', 'thigh', 'shin'):
            values = [result['jointSegmentMeters'].get(key + side) for side in ('Left', 'Right')]
            dimensions[key + 'ProjectedLength'] = float(np.mean(values)) if all(v is not None for v in values) else None
        feet = [np.concatenate([m['position'] for m in meshes if m['part'] == part and m.get('render',True)])
                for part in ('footl','footr') if any(m['part']==part and m.get('render',True) for m in meshes)]
        dimensions['footLength'] = float(np.mean([np.ptp(p[:,1]) for p in feet])) if feet else None
        dimensions['footWidth'] = float(np.mean([np.ptp(p[:,0]) for p in feet])) if feet else None
        head = [m['position'] for m in meshes if m['part']=='head' and m.get('render',True)]
        if head:
            head = np.concatenate(head)
            dimensions['headHeight'] = float(np.ptp(head[:,2]))
            dimensions['headWidth'] = float(np.ptp(head[:,0]))
        result['dimensionsMeters'] = dimensions
        result['dimensionBasis'] = 'exact sections at proposed anatomical fractions; projected reference segments compared to joint distances'
        from .nwn_part_measurements import model_parts
        result['nwnParts'] = model_parts(meshes,joints)
        folder = Path(output) / 'models' / identity
        folder.mkdir(parents=True)
        for view in VIEWS:
            mask, labels, metadata = rasterize(meshes, view)
            Image.fromarray(mask.astype(np.uint8) * 255).save(folder / (view + '.png'))
            # PNG 16-bit labels are sufficient for 16 part owners.
            Image.fromarray(np.asarray(labels).astype(np.uint16)).save(folder / (view + '-parts.png'))
            colors=np.array([[223,152,70],[166,115,214],[90,200,150],[235,205,115],
                [85,150,230],[85,150,230],[95,205,215],[95,205,215],[190,210,240],[190,210,240],
                [215,125,110],[215,125,110],[150,185,80],[150,185,80],[200,170,150],[200,170,150]],dtype=np.uint8)
            palette=np.zeros((len(metadata['parts'])+1,3),dtype=np.uint8)
            for part,number in metadata['parts'].items():
                palette[number]=colors[list(PART_JOINTS).index(part)] if part in PART_JOINTS else [90,90,90]
            indices=np.asarray(labels).astype(int)
            Image.fromarray(palette[indices]).save(folder/(view+'-part-review.png'))
            write(folder / (view + '-raster.json'), metadata)
        write(folder / 'measurements.json', result)
        results[identity], assemblies[identity] = result, meshes
    return results, assemblies


def contour(mask):
    inner = mask.copy()
    inner[1:] &= mask[:-1]
    inner[:-1] &= mask[1:]
    inner[:, 1:] &= mask[:, :-1]
    inner[:, :-1] &= mask[:, 1:]
    yy, xx = np.nonzero(mask & ~inner)
    points = np.column_stack([xx, yy])
    return points[::max(1, int(np.ceil(len(points) / 1000)))].astype(float)


def compare(left, right, pixel_mm=2):
    require(left.shape == right.shape and left.any() and right.any(), 'Comparable nonempty masks required')
    overlap = np.count_nonzero(left & right)
    union = np.count_nonzero(left | right)
    a, b = contour(left), contour(right)
    distances = []
    for source, target in ((a, b), (b, a)):
        for block in np.array_split(source, max(1, int(np.ceil(len(source) / 100)))):
            distances.extend(np.sqrt(((block[:, None] - target[None]) ** 2).sum(axis=2)).min(axis=1).tolist())
    return {'dice': 2 * overlap / (int(left.sum()) + int(right.sum())), 'iou': overlap / union,
            'contourMeanMm': float(np.mean(distances) * pixel_mm),
            'contourP95Mm': float(np.percentile(distances, 95) * pixel_mm),
            'contourSampling': 'deterministic at-most-1000 boundary samples per mask',
            'acceptance': 'diagnostic-only; pose unmatched and references unapproved'}


def metric_canvas(mask, scale, horizontal_min, z_max, ground, center):
    canvas = Image.new('1', (2000, 2000), 0)
    resized = Image.fromarray(mask.astype(np.uint8) * 255).resize(
        (max(1, round(mask.shape[1] * scale / .002)), max(1, round(mask.shape[0] * scale / .002))), Image.Resampling.NEAREST)
    x = round(1000 + (horizontal_min - center) / .002)
    y = round(1800 - (z_max - ground) / .002)
    require(x >= 0 and y >= 0 and x + resized.width <= 2000 and y + resized.height <= 2000,
            'Comparison exceeds metric canvas; do not clip silently')
    canvas.paste(resized.convert('1'), (x, y))
    return np.asarray(canvas, dtype=bool)


def reaudit(config, output, references, models, assemblies, annotations):
    reports = {}
    heights = config['heightTargets']
    for identity, model in models.items():
        if model['role'] not in ('v1-candidate', 'v1-donor'):
            continue
        slug = model['reference']
        race, gender, physique = slug.split('_')
        target_height = heights['referenceHeights'][race][gender] * heights['uniformReferenceScale']
        report = {'id': identity, 'bindStatureMeters': model['bindStatureMeters'],
                  'targetStatureMeters': target_height,
                  'bindStatureErrorPercent': 100 * (model['bindStatureMeters'] / target_height - 1),
                  'runtimeStature': 'unverified; appearance HEIGHT is not proof of geometric scaling',
                  'limitations': ['Upper-body occlusions are excluded without reconstructing hidden skin.',
                                  'Side alignment uses a provisional sheet midline versus the model pelvis; pose is unmatched.',
                                  'Comparative scores do not certify anatomy, equipment or production.'],
                  'views': {}, 'productionAcceptance': False}
        comparator = config['models'][identity].get('stockComparator')
        for view in VIEWS:
            row = annotations[slug]['views'][view]
            ref_mask = np.asarray(Image.open(Path(output) / 'reference' / slug / (view + '-body.png'))) > 0
            # Comparative envelope retains a common horizontal crop; the source
            # review mask itself now preserves shoulders around contour exclusions.
            ref_mask[:max(0,row['bodyTopY']-row['crop'][1])]=False
            ref_scale = target_height / (row['soleY'] - row['crownY'])
            target = metric_canvas(ref_mask, ref_scale, (row['crop'][0] - row['midlineX']) * ref_scale,
                                   (row['soleY'] - row['crop'][1]) * ref_scale, 0, 0)
            values = {}
            for label, model_id in (('candidate', identity), ('stock', comparator), ('humanDonor', 'human-male-v2')):
                if model_id not in models:
                    values[label] = {'status': 'unavailable', 'reason': 'No verified same-slot comparator'}
                    continue
                # Crop at exactly the reference neck fraction, excluding the head consistently.
                raster = np.asarray(Image.open(Path(output) / 'models' / model_id / (view + '.png'))) > 0
                metadata = read(Path(output) / 'models' / model_id / (view + '-raster.json'))
                model_info = models[model_id]
                floor = model_info['boundsMeters'][0][2]
                neck_z = floor + model_info['bindStatureMeters'] * (row['soleY'] - row['bodyTopY']) / (row['soleY'] - row['crownY'])
                cut = max(0, int(np.ceil((metadata['zMax'] - neck_z) / .002)) + 1)
                raster[:cut] = False
                center = model_info['jointPositionsMeters']['pelvis_g'][0 if view in ('front', 'back') else 1]
                if view in ('back', 'right'):
                    center = -center
                occupied = metric_canvas(raster, .002, metadata['horizontalMin'] - .002,
                                         metadata['zMax'] + .002, floor, center)
                values[label] = compare(occupied, target)
                ghost = np.zeros((*target.shape, 3), dtype=np.uint8)
                ghost[target] = (230, 90, 180)
                ghost[occupied] = (80, 220, 140)
                ghost[target & occupied] = (240, 240, 240)
                yy, xx = np.nonzero(target | occupied)
                picture = Image.fromarray(ghost).crop((max(0,int(xx.min())-15),max(0,int(yy.min())-15),
                                                      min(2000,int(xx.max())+16),min(2000,int(yy.max())+16)))
                comparison_dir = Path(output) / 'reaudit-v1' / identity
                comparison_dir.mkdir(parents=True, exist_ok=True)
                picture.save(comparison_dir / (view + '-' + label + '.png'))
            if 'dice' in values['candidate'] and 'dice' in values['stock']:
                values['gainOverSameSlotStockDicePoints'] = 100 * (values['candidate']['dice'] - values['stock']['dice'])
            report['views'][view] = values
        # Quantify local projected overlap independently of the legacy first-array parser.
        joints = model['jointPositionsMeters']
        overlap = {}
        for upper, lower, first, second in [('legl', 'shinl', 'lthigh_g', 'lshin_g'),
                                             ('legr', 'shinr', 'rthigh_g', 'rshin_g'),
                                             ('shinl', 'footl', 'lshin_g', 'lfoot_g'),
                                             ('shinr', 'footr', 'rshin_g', 'rfoot_g')]:
            axis = np.array(joints[second]) - joints[first]
            axis /= np.linalg.norm(axis)
            parent = np.concatenate([m['position'] for m in assemblies[identity] if m['part'] == upper]) @ axis
            child = np.concatenate([m['position'] for m in assemblies[identity] if m['part'] == lower]) @ axis
            overlap[upper + '-' + lower] = max(0, float(min(parent.max(), child.max()) - max(parent.min(), child.min())))
        report['diagnosticAxialOverlapMeters'] = overlap
        report['overlapLimitStatus'] = 'reported; no approved upper limit or visible-anatomy acceptance'
        reports[identity] = report
        write(Path(output) / 'reaudit-v1' / (identity + '.json'), report)
    return reports


def recommendations(config, references, models):
    output = {}
    for slug, reference in references.items():
        race, gender, physique = slug.split('_')
        donor = models['human-' + gender + ('-v2' if gender == 'male' else '-v1')]
        anchor = references['human_' + gender + '_fit']['measurements']
        height = config['heightTargets']['referenceHeights'][race][gender] * config['heightTargets']['uniformReferenceScale']
        if race == 'human':
            height = donor['bindStatureMeters']
        rows = {}
        for key, dimension in donor['dimensionsMeters'].items():
            r, h = reference['measurements'].get(key), anchor.get(key)
            if dimension is None or not r or not h or r['value'] is None or h['value'] is None or h['value'] <= 0:
                rows[key] = {'meters': None, 'status': 'unavailable'}
                continue
            # Covered garment contours remain diagnostic, never fitting targets.
            if 'Clothed' in key:
                rows[key] = {'meters': None, 'status': 'unavailable-covered-anatomy'}
                continue
            rows[key] = {'meters': transfer(dimension, donor['bindStatureMeters'], r['value'], h['value'], height),
                         'referenceRatio': r['value'] / h['value'], 'status': 'proposed-not-approved',
                         'raceViewSpread': r.get('spread'), 'humanViewSpread': h.get('spread'),
                         'raceAnnotationUncertainty': r.get('annotationUncertainty'),
                         'humanAnnotationUncertainty': h.get('annotationUncertainty'), 'tolerance': None}
            if key in ('footWidth','footLength'):
                rows[key]['referenceProjectionScopes']=r.get('projectionScopes',[])
                rows[key]['donorBasis']='mean exact world-projected extent of each NWN foot mesh; standing pose unmatched'
        stock_id = race + '-male-stock'
        mismatch = {}
        if gender == 'male' and physique == 'fit' and stock_id in models:
            for key, target in rows.items():
                actual = models[stock_id]['dimensionsMeters'].get(key)
                if actual is not None and target['meters']:
                    mismatch[key] = 100 * (actual / target['meters'] - 1)
        hints = ['reference approval required', 'runtime stature unverified', 'equipment not evaluated']
        if any(abs(v) > 5 for k, v in mismatch.items() if 'Length' in k):
            hints.append('segment mismatch above 5%; rig/length review needed')
        output[slug] = {'slug': slug, 'proposedStatureMeters': height, 'donor': donor['id'],
                        'measurements': rows, 'stockMismatchPercent': mismatch, 'handoff': hints,
                        'generationPolicy': 'preserve published Human Fit' if race == 'human' and physique == 'fit'
                        else 'defer to Troll target session' if race == 'troll' else 'future fitting proposal',
                        'referenceApproval': False, 'assetApproval': False}
        output[slug]['nwnPartTargets']={part:{'attachmentJoint':mapping['attachmentJoint'],
            'dimensions':{key:rows.get(key,{'meters':None,'status':'unavailable'}) for key in mapping['sourceMeasurements']},
            'donorMeasurementPart':part,'referenceBoundaryStatus':mapping['boundaryStatus'],
            'approval':False} for part,mapping in reference['nwnParts'].items()}
    return output


def review_index(output, references, models, proposals, audits):
    output = Path(output)
    head = '<!doctype html><meta charset="utf-8"><title>Phenotype measurements v2</title><style>body{font:16px system-ui;background:#15191e;color:#eef2f5;margin:30px}a{color:#80c8ff}img{max-width:100%}article{margin:30px 0;padding:20px;background:#232a32}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #526070}pre{white-space:pre-wrap}</style>'
    sections = [head, '<h1>Phenotype measurements v2</h1><p>Measurement proposals only. References pending user approval. Runtime scale unverified. No bodies, rigs, equipment, packs or client state changed.</p>',
                '<p><a href="ledger.json">Evidence ledger</a> · <a href="generation-handoff.json">Generation handoff</a> · <a href="historical-findings.json">Historical defect reproduction</a></p>',
                '<h2>Existing model assemblies</h2><table><tr><th>Model</th><th>Bind height (m)</th><th>Meshes</th><th>Evidence</th></tr>']
    for identity, result in models.items():
        sections.append(f'<tr><td>{html.escape(identity)}</td><td>{result["bindStatureMeters"]:.6f}</td><td>{result["meshCount"]}</td><td><a href="models/{identity}/measurements.json">Measurements</a> · <a href="models/{identity}/front.png">Front</a> · <a href="models/{identity}/left.png">Side</a> · <a href="models/{identity}/back.png">Rear</a></td></tr>')
        if result.get('stockSlotNote'):
            sections.append(f'<tr><td colspan="4">{html.escape(result["stockSlotNote"])}</td></tr>')
        sections.append(f'<tr><td colspan="4"><a href="models/{identity}/front-part-review.png">NWN part ownership · front</a> · <a href="models/{identity}/left-part-review.png">side</a> · <a href="models/{identity}/back-part-review.png">rear</a><details><summary>Part dimensions in attachment coordinates</summary><table><tr><th>Part</th><th>Joint</th><th>Local X / Y / Z extent (m)</th><th>Joint distance (m)</th></tr>')
        for part, value in result['nwnParts'].items():
            extent=' / '.join(f'{x:.4f}' for x in value.get('localExtentMeters',[])) or 'unavailable'
            length=value.get('jointDistanceMeters')
            sections.append(f'<tr><td>{part}</td><td>{value["attachmentJoint"]}</td><td>{extent}</td><td>{length:.4f}</td></tr>' if length is not None else f'<tr><td>{part}</td><td>{value["attachmentJoint"]}</td><td>{extent}</td><td>unavailable</td></tr>')
        sections.append('</table></details></td></tr>')
    sections.append('</table><h2>Reference masks and proposed targets</h2>')
    for slug, result in references.items():
        sections.append(f'<article><h3>{html.escape(slug)}</h3><p>Approval pending · View stature spread: {100 * result["viewStatureDisagreement"]:.2f}% · {html.escape(", ".join(result["flags"]))}</p><img src="reference/{slug}/overlay.png"><p><a href="reference/{slug}/source-sheet.png">Regenerated source sheet</a> · <a href="reference/{slug}/measurements.json">Measurements and uncertainty</a> · <a href="proportions/{slug}.json">Proposed proportions</a></p><pre>{html.escape(json.dumps(proposals[slug]["handoff"], indent=2))}</pre></article>')
    sections.append('<h2>v1 re-audit</h2><p>All overlap scores are diagnostic: standing poses are unmatched and references are unapproved. Bind-height error does not establish runtime-height error.</p>')
    for identity, report in audits.items():
        sections.append(f'<p><a href="reaudit-v1/{identity}.json">{identity}</a>: bind stature {report["bindStatureMeters"]:.6f} m; calibrated target {report["targetStatureMeters"]:.6f} m; bind-height difference {report["bindStatureErrorPercent"]:+.2f}%.</p>')
        sections.append('<p>White: overlap · Green: model only · Magenta: reference only. Fixed 2 mm/pixel; head/occlusion bands excluded.</p>')
        for view in ('front','left','back'):
            sections.append(f'<a href="reaudit-v1/{identity}/{view}-candidate.png"><img style="max-height:360px;max-width:30%" src="reaudit-v1/{identity}/{view}-candidate.png" alt="{identity} {view} contour comparison"></a>')
    (output / 'index.html').write_text('\n'.join(sections), encoding='utf-8')


def historical_findings(config, output, references, models, audits, evidence):
    from .build_silhouette_comparison_sheet import extract_concept_mask
    helpers = [Path(__file__).with_name(name) for name in
               ('build_silhouette_comparison_sheet.py', 'calculate_silhouette_difference.py', 'audit_geometry.py')]
    evidence.extend(verified(p, sha(p)) for p in helpers)
    slug = 'troll_male_fit'
    image = Image.open(references[slug]['source']['path']).convert('RGB')
    annotation = read(Path(config['referenceConfig']) / 'exclusions' / (slug + '.json'))['views']['front']
    box = annotation['crop']; raw = np.asarray(image)[:,box[0]:box[2]]
    rows = np.flatnonzero(np.any(raw > 20, axis=(1,2)))
    _, legacy_height, _ = extract_concept_mask(image, (box[0],box[2]))
    items = [
        {'claim':'Legacy concept extraction includes title/view labels', 'status':'reproduced',
         'source':references[slug]['source'], 'legacyRows':[int(rows[0]),int(rows[-1])],
         'legacyExtentPixels':int(legacy_height),
         'annotatedCrownSole':[annotation['crownY'],annotation['soleY']]},
        {'claim':'Dwarf v1 stature is 1.4864 m', 'status':'contradicted-by-restored-geometry',
         'measuredBindMeters':models['dwarf-male-v1']['bindStatureMeters'],
         'basis':'Complete hash-verified assembly with all mesh transforms and selected stock head/neck'},
        {'claim':'Elf knee/ankle overlap', 'status':'measured-diagnostic-only',
         'axialOverlapMeters':audits['elf-male-v1']['diagnosticAxialOverlapMeters'],
         'limits':'Projected extent intersection; does not prove contact or motion acceptance'},
        {'claim':'Pelvis multi-mesh omission risk', 'status':'complete-inventory-reproduced',
         'meshes':[r for r in models['human-male-v1']['meshInventory'] if r['part']=='pelvis'],
         'limits':'Historical first-array acceptance run was not replayed'},
        {'claim':'Historical thresholds, rear-half swaps and stale gate receipts', 'status':'not-reproduced',
         'reason':'Historical rendered comparisons and certifying receipts were not consumed; current re-audit uses correct source sheets and same-slot stock controls'},
        {'claim':'Historical runtime scale and animation/client stature claims', 'status':'not-reproduced',
         'reason':'No controlled client experiment in this release; runtime scaling remains unverified'}]
    write(Path(output)/'historical-findings.json', {'helpers':[pin(p) for p in helpers], 'findings':items,
          'productionAcceptance':False, 'historicalEvidenceModified':False})


def run(config_path, output, pilot=False):
    started = time.monotonic()
    config, output = read(config_path), Path(output)
    require(not output.exists(), 'Fresh versioned measurement output required')
    evidence = [verified(config_path, sha(config_path))]
    for key in ('heightSource', 'archiveManifest', 'stockExtraction', 'migration'):
        evidence.append(verified(config[key]['path'], config[key]['sha256']))
    if pilot:
        config['models'] = {name: value for name, value in config['models'].items()
                            if value['reference'] in ('human_male_fit', 'dwarf_male_fit')}
    for manifest in config['donors']:
        path = Path(manifest['path'])
        evidence.append(verified(path, manifest['sha256']))
        value = read(path)
        require(value['productionAccepted'] is True, 'Donor not finalized')
        for row in value['resources']:
            resource_path = safe_relative(config['repository'], row['path'])
            evidence.append(verified(resource_path, row['sha256']))
    output.mkdir(parents=True)
    config_dir = Path(config['referenceConfig'])
    references = reference_batch(config_dir, output, config['referenceRoot'], evidence, pilot)
    models, assemblies = model_batch(config, output, references, evidence)
    annotations = {slug: read(config_dir / 'exclusions' / (slug + '.json')) for slug in references}
    proposals = recommendations(config, references, models)
    for slug, value in proposals.items():
        write(output / 'proportions' / (slug + '.json'), value)
    audits = reaudit(config, output, references, models, assemblies, annotations)
    if not pilot:
        historical_findings(config, output, references, models, audits, evidence)
    else:
        write(output/'historical-findings.json', {'status':'pilot-only; full historical reproduction deferred to complete batch'})
    review_index(output, references, models, proposals, audits)
    write(output / 'generation-handoff.json', {'targets': proposals, 'rigPoliciesApproved': False,
          'limits': ['Existing affine tooling is a candidate only; joint/connector and equipment review remain mandatory.',
                    'No silhouette-length measurement alone establishes a custom rig requirement.',
                    'Head anatomy hidden by hair/horns and covered garment contours are not fitting authority.'],
          'nextAction': 'Review masks/landmarks, then verify runtime scale before selecting fitting/rig policies.'})
    evidence.extend(pin(p) for p in sorted(output.rglob('*')) if p.is_file())
    direction_sequence=config.get('directionSequence',1)
    ledger = {'kind': 'phenotype-measurement-ledger', 'schemaVersion': 1, 'currentDirectionSequence': direction_sequence,
        'partsBank': config['donors'], 'targetRevision': 'measurements-v2', 'toolMigration': config['migration'],
        'latestDirection': {'sequence': direction_sequence, 'superseded': False,
                            'instruction': config.get('direction','Implement measurement-only v2; male v2 donor, preserved Human Fit and Troll authority.')},
        'priorReferenceApproval':config.get('priorReferenceApproval'),
        'rejectedAlternatives': ['Body/rig/equipment regeneration in this release', 'Inventing hidden anatomy'],
        'blockers': ['Reference approval pending', 'Runtime stature unverified'],
        'nextAction': 'Review index.html and hash-bound reference annotations before any fitting.',
        'referenceApproval': False, 'workingSelection': None, 'nativeValidation': None,
        'clientValidation': None, 'productionAcceptance': False,
        'evidence': list({p['path']: p for p in evidence}.values()), 'elapsedSeconds': time.monotonic() - started}
    write(output / 'ledger.json', ledger)
    fields = ('partsBank', 'targetRevision', 'toolMigration', 'latestDirection', 'rejectedAlternatives', 'blockers',
              'nextAction', 'referenceApproval', 'workingSelection', 'nativeValidation', 'clientValidation', 'productionAcceptance')
    write(output / 'resume-bindings.json', {'ledger': pin(output / 'ledger.json'),
          'selectors': {field: '/' + field for field in fields}, 'dependencies': ledger['evidence']})
    print(json.dumps({'output': str(output.resolve()), 'referenceSheets': len(references),
                      'modelAssemblies': len(models), 'v1Audits': len(audits), 'seconds': ledger['elapsedSeconds']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('smoke')
    p = sub.add_parser('stock-plan'); p.add_argument('--game-root', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('stock-extract'); p.add_argument('--plan', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('run'); p.add_argument('--config', type=Path, required=True); p.add_argument('--output', type=Path, required=True); p.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    if args.command == 'smoke': smoke()
    elif args.command == 'stock-plan': prepare_stock(args.game_root, args.output)
    elif args.command == 'stock-extract':
        verified(args.plan, sha(args.plan)); print(json.dumps({'extracted': len(extract(read(args.plan), args.output))}))
    else: run(args.config, args.output, args.pilot)
