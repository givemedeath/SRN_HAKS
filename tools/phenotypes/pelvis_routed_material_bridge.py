"""Typed routed pelvis skin/brief compiler material inputs for one sealed current native pelvis geometry.

Compiler slots come only from a pinned typed-slot contract and its face-routing lineage: original-atlas skin,
generated caps on the same original atlas, two typed extra skin atlases (skin1/skin2) carrying their own embedded
colour/normal/ORM, and the virtual brief (compiler slot 4) as an opaque garment on the unchanged original atlas.
Every skin atlas receives the same single gain/offset AO0 calibration with the existing quantization and
palette-before-filter policy, so the patch atlases convert to PLT exactly like the original atlas.
Writes nothing; no selection, client or production acceptance.
"""
from pathlib import Path
import json
import numpy as np
import target_contract as c
import replay_stage_skin_calibration as cal
from place_purposebuilt_pelvis import read_glb, raw_corners

MODE = 'current-pelvis-routed-skin-calibration-v1'
KIND = 'separately-verified-current-geometry-and-pelvis-routed-calibration-material-inputs'
SLOTS_KIND = 'target-pelvis-typed-material-slots-contract'
RECIPE_KIND = 'target-pelvis-routed-skin-calibration-recipe'
SLOTS = {'0': {'role': 'skin', 'atlasKey': 'skin', 'documentMaterialId': 0},
         '1': {'role': 'skin', 'atlasKey': 'skin', 'documentMaterialId': 1},
         '2': {'role': 'skin', 'atlasKey': 'skin1', 'documentMaterialId': 2},
         '3': {'role': 'skin', 'atlasKey': 'skin2', 'documentMaterialId': 3},
         '4': {'role': 'garment', 'atlasKey': 'garment', 'documentMaterialId': 0, 'virtualCompilerOwnershipOnly': True}}
SKIN_ATLASES = ('skin', 'skin1', 'skin2')
SLOT_FIELDS = {'schemaVersion', 'kind', 'diagnosticOnly', 'targetContract', 'targetContractSha256', 'targetId', 'rigRevision', 'coordinateSpace',
               'part', 'model', 'candidate', 'geometryReceipt', 'faceRouting', 'sourceSlots', 'slots', 'pltReadyArrays', 'briefFaces',
               'compilerFaceCounts', 'selected'}
RECIPE_FIELDS = {'schemaVersion', 'kind', 'diagnosticOnly', 'targetContract', 'targetContractSha256', 'targetId', 'rigRevision', 'coordinateSpace',
                 'part', 'candidate', 'geometryReceipt', 'materialSlots', 'gain', 'offsetBytes', 'offsetBasis', 'atlasAO0IntensitySha256',
                 'calibratedAO0IntensitySha256', 'quantization', 'palettePolicy', 'calibrationApplications', 'parentAoStrength', 'aoStrength', 'selected'}
ROUTING_FIELDS = ('documentFaceMaterialIds', 'compilerFaceMaterialIds', 'fixedMainBriefFaceMask')


def read(row):
    p = cal.exact_pin(row); return p, json.loads(p.read_text(encoding='utf-8'))


def controls(value):
    c.require(isinstance(value, dict) and set(value) == {'mode', 'recipe', 'materialSlots'} and value['mode'] == MODE,
              'Exact pelvis routed calibration controls required')
    for key in ('recipe', 'materialSlots'):
        cal.exact_pin(value[key])


def typed_slots():
    """Stage-facing typed slots: exactly role and atlas key per compiler material."""
    return {k: {'role': v['role'], 'atlasKey': v['atlasKey']} for k, v in SLOTS.items()}


def compiler_ids(document_ids, compiler, brief, brief_faces):
    """Compiler ids equal document ids except the declared brief, which is exactly virtual slot 4 on document 0."""
    document_ids, compiler, brief = np.asarray(document_ids), np.asarray(compiler), np.asarray(brief)
    c.require(document_ids.dtype.kind in 'iu' and compiler.dtype.kind in 'iu' and brief.dtype == np.dtype(bool)
              and document_ids.shape == compiler.shape == brief.shape and document_ids.ndim == 1, 'Exact typed face routing arrays required')
    c.require(set(np.unique(compiler).tolist()) == {int(k) for k in SLOTS} and np.array_equal(compiler, np.where(brief, 4, document_ids))
              and int(brief.sum()) == brief_faces, 'Compiler routing differs from document ownership and declared brief')
    for key, row in SLOTS.items():
        c.require(np.all(document_ids[compiler == int(key)] == row['documentMaterialId']), 'Compiler slot draws faces from another document material')
    return compiler.astype(np.int64)


def calibrated_rows(rows, gain, offset, ao_red, ao_strength=0):
    """One shared AO0 affine calibration for every skin atlas; maps, cloth and parents never change."""
    c.require(set(rows) == set(SKIN_ATLASES) | {'garment'} and set(ao_red) == set(SKIN_ATLASES) and ao_strength == 0,
              'Complete pelvis skin/garment rows and AO0 required')
    out = {k: dict(v) for k, v in rows.items()}; stats = {}
    for key in SKIN_ATLASES:
        value, aux = cal.calibrated_intensity(rows[key]['intensity'], ao_red[key], gain, offset, ao_strength)
        out[key]['intensity'] = value
        stats[key] = {'parentAO0IntensitySha256': cal.fingerprint(rows[key]['intensity']), 'calibratedAO0IntensitySha256': cal.fingerprint(aux['calibratedAO0']),
                      'effectiveIntensitySha256': cal.fingerprint(value), 'clampedLowTexels': int(aux['clampedLow'].sum()),
                      'clampedHighTexels': int(aux['clampedHigh'].sum()), 'sourceAO0Contrast': cal.contrast(rows[key]['intensity']),
                      'effectiveIntensityContrast': cal.contrast(value)}
    for key, row in out.items():
        for name in ('color', 'normal', 'roughness'):
            c.require(np.array_equal(row[name], rows[key][name]), 'Protected source pixels changed')
    return out, stats


def bilinear(atlas, uv):
    """Clamp-to-edge base-level bilinear sample of a per-texel RGB/byte atlas at glTF UVs."""
    h, w = atlas.shape[:2]; x = np.clip(uv[:, 0] * w - .5, 0, w - 1); y = np.clip(uv[:, 1] * h - .5, 0, h - 1)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); x1 = np.minimum(x0 + 1, w - 1); y1 = np.minimum(y0 + 1, h - 1)
    fx = (x - x0)[:, None]; fy = (y - y0)[:, None]; a = atlas.astype(float).reshape(h, w, -1)
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy) + a[y1, x0] * (1 - fx) * fy + a[y1, x1] * fx * fy)


def seam_samples(positions, uv, atlas_of_face, pairs, samples=5):
    """UV pairs sampled along exact shared 3D edges whose two faces use atlas pairs; returns {pair: (uvA, uvB)}.

    A same-atlas pair keeps only UV-discontinuous edges (existing texture seams, the reference distribution)."""
    _, ids = np.unique(positions.reshape(-1, 3), axis=0, return_inverse=True); f = ids.reshape(-1, 3)
    rows = {}
    for corner_a, corner_b in ((0, 1), (1, 2), (2, 0)):
        for face in range(len(f)):
            rows.setdefault((min(f[face, corner_a], f[face, corner_b]), max(f[face, corner_a], f[face, corner_b])), []).append((face, corner_a, corner_b))
    t = (np.arange(samples) + .5) / samples; out = {p: ([], []) for p in pairs}
    for key, owners in rows.items():
        if len(owners) != 2:
            continue
        (fa, a0, a1), (fb, b0, b1) = owners; ka, kb = atlas_of_face[fa], atlas_of_face[fb]
        pair = (ka, kb) if (ka, kb) in out else (kb, ka) if (kb, ka) in out else None
        if pair is None:
            continue
        if pair != (ka, kb):
            fa, a0, a1, fb, b0, b1 = fb, b0, b1, fa, a0, a1
        # Align endpoints by exact vertex identity, then sample both UV parameterizations of the same 3D edge.
        if f[fa, a0] != f[fb, b0]:
            b0, b1 = b1, b0
        if ka == kb and np.array_equal(uv[fa, [a0, a1]], uv[fb, [b0, b1]]):
            continue
        ua = uv[fa, a0][None] * (1 - t[:, None]) + uv[fa, a1][None] * t[:, None]; ub = uv[fb, b0][None] * (1 - t[:, None]) + uv[fb, b1][None] * t[:, None]
        out[pair][0].append(ua); out[pair][1].append(ub)
    return {p: (np.concatenate(a) if a else np.zeros((0, 2)), np.concatenate(b) if b else np.zeros((0, 2))) for p, (a, b) in out.items()}


def palette_seam_report(samples, intensity, palette, rows=(3, 8)):
    """Per atlas pair: intensity and palette RGB (LUT before filtering) differences across shared edges."""
    report = {}
    for (ka, kb), (ua, ub) in samples.items():
        name = ka + '|' + kb
        if not len(ua):
            report[name] = {'samples': 0}; continue
        di = np.abs(bilinear(intensity[ka], ua)[:, 0] - bilinear(intensity[kb], ub)[:, 0])
        row = {'samples': int(len(ua)), 'intensityAbsBytes': {'mean': float(di.mean()), 'p95': float(np.percentile(di, 95)), 'max': float(di.max())},
               'signedIntensityMeanBytes': float((bilinear(intensity[ka], ua)[:, 0] - bilinear(intensity[kb], ub)[:, 0]).mean()), 'palettes': {}}
        for r in rows:
            ra = bilinear(cal.palette_texels(intensity[ka], palette, r), ua); rb = bilinear(cal.palette_texels(intensity[kb], palette, r), ub)
            d = np.abs(ra - rb).mean(1)
            row['palettes'][str(r)] = {'meanAbsRGB': float(d.mean()), 'p95AbsRGB': float(np.percentile(d, 95)), 'maxAbsRGB': float(d.max()),
                                       'signedMeanRGB': (ra - rb).mean(0).tolist()}
        report[name] = row
    return report


def staging_inputs(value, target_path, target, part, space, source, receipt, ao_strength=0, native_geometry=None):
    controls(value)
    from native_compiler_input_bridge import VerifiedNativeCompilerInputs
    from target_part_stage import material_inputs, image_pixels
    c.require(type(native_geometry) is VerifiedNativeCompilerInputs, 'Sealed current native geometry context required')
    c.require(part == 'pelvis' and space == 'working' and ao_strength == 0, 'Pelvis routed calibration supports the working pelvis at AO0 only')
    native_geometry.verify(); gp = dict(native_geometry.proof); pins = dict(gp['frozenInputs'])
    source = Path(source).resolve(); receipt = Path(receipt).resolve(); rec = json.loads(receipt.read_text(encoding='utf-8'))
    source_pin = {'path': str(source), 'sha256': c.sha(source)}; receipt_pin = {'path': str(receipt), 'sha256': c.sha(receipt)}
    c.verify_binding(rec, target_path, target, space)
    c.require(gp['part'] == part and gp['candidate'] == source_pin and gp['geometryReceipt'] == receipt_pin, 'Cross-owner/current native geometry context')
    c.require(rec['part'] == part and Path(rec['candidate']).resolve() == source and rec['candidateSha256'] == source_pin['sha256'], 'Current material source/owner differs')
    sp, slots = read(value['materialSlots']); rp, recipe = read(value['recipe']); pins.update({str(sp): c.sha(sp), str(rp): c.sha(rp)})
    for doc_, fields, kind in ((slots, SLOT_FIELDS, SLOTS_KIND), (recipe, RECIPE_FIELDS, RECIPE_KIND)):
        c.require(isinstance(doc_, dict) and set(doc_) == fields and doc_['kind'] == kind and type(doc_['schemaVersion']) is int and doc_['schemaVersion'] == 1
                  and doc_['diagnosticOnly'] is True and doc_['selected'] is False and doc_['part'] == part, 'Exact diagnostic pelvis slot/recipe contract required')
        c.verify_binding(doc_, target_path, target, 'working')
        c.require(doc_['candidate'] == source_pin and doc_['geometryReceipt'] == receipt_pin, 'Slot/recipe contract binds another geometry')
    c.require(recipe['materialSlots'] == value['materialSlots'] and slots['model'] == c.model(target, part) and slots['slots'] == SLOTS, 'Recipe/slot contract binding differs')
    sourceslots_path, sourceslots = read(slots['sourceSlots']); pins[str(sourceslots_path)] = c.sha(sourceslots_path)
    c.require(sourceslots['slots'] == SLOTS and sourceslots['faceOwnership']['sha256'] == slots['faceRouting']['sha256'], 'Typed slots differ from the adopted descendant slots')
    lp = cal.exact_pin(slots['faceRouting']); pins[str(lp)] = c.sha(lp)
    with np.load(lp, allow_pickle=False) as z:
        routing = {k: z[k].copy() for k in ROUTING_FIELDS}
    doc, binary = read_glb(source); document_ids = np.asarray([x['material'] for x in raw_corners(doc, binary)[3] for _ in range(x['triangles'])], dtype=np.int64)
    c.require(np.array_equal(native_geometry.material_ids, document_ids) and np.array_equal(routing['documentFaceMaterialIds'], document_ids),
              'Routing lineage differs from sealed document face ownership')
    ids = compiler_ids(document_ids, routing['compilerFaceMaterialIds'], routing['fixedMainBriefFaceMask'], slots['briefFaces'])
    counts = {str(k): int((ids == k).sum()) for k in range(5)}; c.require(counts == slots['compilerFaceCounts'], 'Compiler face counts differ')
    roles = {int(k): v['role'] for k, v in SLOTS.items() if k != '4'}; keys = {int(k): v['atlasKey'] for k, v in SLOTS.items() if k != '4'}
    rows, transport = material_inputs(doc, binary, roles, part, 0, c.fixed_garment_parts(target), atlas_keys=keys)
    c.require(set(rows) == set(SKIN_ATLASES), 'Exact typed skin atlases required')
    for key in ('skin1', 'skin2'):
        ap = cal.exact_pin(slots['pltReadyArrays'][key]); pins[str(ap)] = c.sha(ap)
        with np.load(ap, allow_pickle=False) as z:
            c.require(np.array_equal(z['colorRGB'], rows[key]['color']) and np.array_equal(z['AO0RawIntensity'], rows[key]['intensity']),
                      'Typed atlas PLT-ready arrays differ from embedded material pixels')
    c.require(set(slots['pltReadyArrays']) == {'skin1', 'skin2'}, 'Exact extra-atlas PLT-ready arrays required')
    c.require(recipe['atlasAO0IntensitySha256'] == {k: cal.fingerprint(rows[k]['intensity']) for k in SKIN_ATLASES}, 'Untreated AO0 atlas intensities differ')
    rows['garment'] = {k: v.copy() for k, v in rows['skin'].items()}
    transport.append({'material': 4, 'role': 'garment', 'atlasKey': 'garment', 'documentMaterial': 0, 'virtualCompilerOwnershipOnly': True,
                      'policy': 'Brief faces keep document material 0 maps; opaque garment colour is the unchanged original atlas'})
    ao_red = {}; provenance = {}
    for key, material in (('skin', 0), ('skin1', 2), ('skin2', 3)):
        binding = doc['materials'][material].get('occlusionTexture')
        ao_red[key] = image_pixels(doc, binary, binding)[:, :, 0] if binding is not None else np.full((2048, 2048), 255, np.uint8)
        provenance[key] = {'material': material, 'effectiveAOredSha256': cal.fingerprint(ao_red[key]), 'aoApplied': False}
    cal.coefficients(recipe['gain'], recipe['offsetBytes'])
    c.require(recipe['quantization'] == cal.QUANTIZATION and recipe['palettePolicy'] == cal.PALETTE and recipe['calibrationApplications'] == 1
              and recipe['parentAoStrength'] == 0 and recipe['aoStrength'] == 0, 'One AO0 calibration with exact quantization/palette policy required')
    bp, basis = read(recipe['offsetBasis']['plan']); pins[str(bp)] = c.sha(bp)
    c.require(set(recipe['offsetBasis']) == {'plan', 'control'} and recipe['offsetBasis']['control'] == 'uniformJointTreeControl.pelvis'
              and basis['uniformJointTreeControl']['pelvis'] == {**basis['uniformJointTreeControl']['pelvis'], 'gain': recipe['gain'], 'offsetBytes': recipe['offsetBytes']},
              'Calibration coefficients differ from the shared joint-tree plan')
    effective, stats = calibrated_rows(rows, recipe['gain'], recipe['offsetBytes'], ao_red, ao_strength)
    c.require(recipe['calibratedAO0IntensitySha256'] == {k: v['calibratedAO0IntensitySha256'] for k, v in stats.items()}, 'Calibrated AO0 intensities differ from the recipe')
    for name in ('pelvis_routed_material_bridge.py', 'current_skin_calibration_bridge.py', 'replay_stage_skin_calibration.py', 'target_part_stage.py',
                 'place_purposebuilt_pelvis.py', 'target_contract.py', 'native_compiler_input_bridge.py'):
        p = Path(__file__).with_name(name).resolve(); pins[str(p)] = c.sha(p)
    for p, h in pins.items():
        c.require(c.sha(p) == h, 'Current material bridge input changed: ' + p)
    native_geometry.verify()
    proof = {'kind': KIND, 'part': part, 'coordinateSpace': 'working', 'mode': MODE, 'recipe': value['recipe'], 'materialSlots': value['materialSlots'],
             'currentNativeGeometryProof': gp, 'typedSlots': SLOTS, 'compilerFaceCounts': counts, 'compilerMaterialIdsSha256': cal.fingerprint(ids),
             'gain': recipe['gain'], 'offsetBytes': recipe['offsetBytes'], 'offsetBasis': recipe['offsetBasis'], 'quantization': cal.QUANTIZATION,
             'palettePolicy': cal.PALETTE, 'atlasCalibration': stats, 'aoStrength': 0, 'aoProvenance': provenance, 'calibrationApplications': 1,
             'sharedCalibrationAcrossSkinAtlases': True, 'briefVirtualGarmentOnOriginalAtlas': True, 'garmentPaddingDerived': False,
             'sourceRGBNormalORMUVAndAuthoredAttributesEdited': False, 'runtimeConversions': 0, 'selected': False, 'clientAccepted': False, 'productionAccepted': False,
             'limits': 'Uniform AO0 calibration only. Skin/brief bilinear texel bleed across the brief UV boundary is not padded; patch tone continuity, palette 3/8 native and client views require review.'}
    return {'document': doc, 'binary': binary, 'materialRoles': {int(k): v['role'] for k, v in SLOTS.items()}, 'materialRows': effective,
            'originalMaterialProof': transport, 'sourceReceipt': rec, 'proof': proof, 'frozenInputs': pins, 'auditFiles': [Path(p) for p in pins],
            'compilerMaterialIds': ids, 'materialSlots': typed_slots()}
