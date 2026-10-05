"""Literal cap pixels and append-only storage; no real source export in tests."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
import diagnostic_pelvis_cap_skin_material as cap
import target_contract as tc
from test_target_part_pipeline import target_fixture


def source_fixture(alpha=255):
    doc = {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': 0}],
           'bufferViews': [], 'accessors': [], 'images': [], 'textures': [],
           'samplers': [{'magFilter': 9729, 'minFilter': 9729, 'wrapS': 33071, 'wrapT': 33071}],
           'materials': [], 'meshes': [{'primitives': []}]}
    blob = bytearray()
    def append(data):
        blob.extend(b'\0' * ((-len(blob)) % 4))
        view = len(doc['bufferViews'])
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(blob), 'byteLength': len(data)})
        blob.extend(data)
        return view
    def array(data, kind, component):
        i = len(doc['accessors'])
        doc['accessors'].append({'bufferView': append(data.tobytes()), 'componentType': component,
                                 'count': len(data), 'type': kind})
        return i
    attrs = {'POSITION': array(np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], '<f4'), 'VEC3', 5126),
             'NORMAL': array(np.tile([0., 0., 1.7], (3, 1)).astype('<f4'), 'VEC3', 5126),
             'TANGENT': array(np.tile([1.3, 0., 0., -1.], (3, 1)).astype('<f4'), 'VEC4', 5126),
             'TEXCOORD_0': array(np.array([[0, 0], [1, 0], [0, 1]], '<f4'), 'VEC2', 5126)}
    indices = array(np.array([0, 1, 2], '<u4'), 'SCALAR', 5125)
    y, x = np.indices((6, 6)); color = np.stack([11+x, 31+y, 51+x+y, np.full((6, 6), alpha)], axis=-1).astype('u1')
    orm = np.stack([np.full((6, 6), 201), 70+x+6*y, np.full((6, 6), 7), np.full((6, 6), 255)], axis=-1).astype('u1')
    normal = np.full((6, 6, 4), [125, 133, 254, 255], 'u1')
    for data in [color, normal, orm]:
        stream = io.BytesIO(); Image.fromarray(data).save(stream, format='PNG')
        doc['images'].append({'bufferView': append(stream.getvalue()), 'mimeType': 'image/png'})
        doc['textures'].append({'source': len(doc['images'])-1, 'sampler': 0})
    body = {'name': 'authored-body', 'normalTexture': {'index': 1, 'scale': 1.},
            'occlusionTexture': {'index': 2, 'strength': 1.},
            'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}, 'metallicRoughnessTexture': {'index': 2},
                                     'baseColorFactor': [.6, .7, .8, 1.], 'roughnessFactor': .8, 'metallicFactor': .0}}
    doc['materials'] = [body, {'name': 'neutral-cap'}, {'name': 'opaque-underwear', 'alphaMode': 'OPAQUE'}]
    for material in [0, 1, 1, 2, 0, 2]:
        doc['meshes'][0]['primitives'].append({'attributes': copy.deepcopy(attrs), 'indices': indices, 'material': material})
    doc['buffers'][0]['byteLength'] = len(blob)
    return doc, bytes(blob), color, orm


class CapMaterialTests(unittest.TestCase):
    def test_exact_pixels_orm_green_and_original_geometry_storage(self):
        doc, blob, color, orm = source_fixture()
        child, data, proof = cap.append_skin_patch(doc, blob, [1, 1, 4, 4])
        cap.prove_storage(doc, blob, child, data, proof)
        self.assertEqual(data[:len(blob)], blob)
        self.assertEqual(proof['literalCrops']['color']['pixelValues'], color[1:4, 1:4].tolist())
        self.assertEqual(proof['literalCrops']['orm']['pixelValues'], orm[1:4, 1:4].tolist())
        self.assertEqual(proof['literalCrops']['orm']['pixelByteSHA256'], hashlib.sha256(orm[1:4, 1:4].tobytes()).hexdigest())
        for name, expected in [('color', color), ('orm', orm)]:
            index = child['materials'][3]['pbrMetallicRoughness']['baseColorTexture' if name == 'color' else 'metallicRoughnessTexture']['index']
            image = child['images'][child['textures'][index]['source']]
            view = child['bufferViews'][image['bufferView']]
            actual = np.asarray(Image.open(io.BytesIO(data[view['byteOffset']:view['byteOffset']+view['byteLength']])).convert('RGBA'))
            np.testing.assert_array_equal(actual, expected[1:4, 1:4])
            self.assertEqual(child['textures'][index]['sampler'], 0)
        self.assertEqual(doc['materials'], child['materials'][:3])
        self.assertEqual(doc['materials'][0]['normalTexture'], child['materials'][0]['normalTexture'])
        self.assertNotIn('normalTexture', child['materials'][3]); self.assertNotIn('occlusionTexture', child['materials'][3])
        self.assertEqual([p['material'] for p in child['meshes'][0]['primitives']], [0, 3, 3, 2, 0, 2])
        for i in [0, 3, 4, 5]: self.assertEqual(child['meshes'][0]['primitives'][i], doc['meshes'][0]['primitives'][i])

    def test_pbr_defaults_and_authored_factors_are_exact_not_retuned(self):
        self.assertEqual(cap.effective_factors({}), {'baseColorFactor': [1., 1., 1., 1.], 'roughnessFactor': 1., 'metallicFactor': 1.})
        doc, blob, _, _ = source_fixture(); child, _, proof = cap.append_skin_patch(doc, blob, [1, 1, 4, 4])
        for key, value in proof['effectiveAdjacentSkinFactors'].items(): self.assertEqual(child['materials'][3]['pbrMetallicRoughness'][key], value)
        for value in [[1, 1, 1], [1, 1, float('nan'), 1]]:
            with self.assertRaises(ValueError): cap.effective_factors({'pbrMetallicRoughness': {'baseColorFactor': value}})

    def test_padded_native_glb_reopen_is_exact_and_transparency_rejected(self):
        doc, blob, _, _ = source_fixture(); child, data, proof = cap.append_skin_patch(doc, blob, [1, 1, 4, 4])
        self.assertEqual(len(data) % 4, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'synthetic.glb'; cap.write_glb(path, child, data)
            reopened, binary = cap.read_glb(path)
            self.assertEqual(reopened, child); self.assertEqual(binary, data)
            cap.prove_storage(doc, blob, reopened, binary, proof)
        for alpha in [0, 128, 254]:
            doc, blob, _, _ = source_fixture(alpha)
            with self.assertRaises(ValueError): cap.append_skin_patch(doc, blob, [1, 1, 4, 4])

    def test_original_bin_material_uv_and_descriptor_mutations_rejected(self):
        doc, blob, _, _ = source_fixture(); child, data, proof = cap.append_skin_patch(doc, blob, [1, 1, 4, 4])
        changed = bytearray(data); changed[0] ^= 1
        with self.assertRaises(ValueError): cap.prove_storage(doc, blob, child, bytes(changed), proof)
        for mutate in [lambda d: d['materials'][0].update(name='different'),
                       lambda d: d['accessors'][3].update(count=2),
                       lambda d: d['textures'][0].update(sampler=7),
                       lambda d: d['meshes'][0]['primitives'][3].update(material=3),
                       lambda d: d['materials'][3].update(normalTexture={'index': 1})]:
            bad = copy.deepcopy(child); mutate(bad)
            with self.assertRaises(ValueError): cap.prove_storage(doc, blob, bad, data, proof)

    def test_ambiguous_parent_uv_transform_extension_and_bad_rectangle_rejected(self):
        doc, blob, _, _ = source_fixture()
        for rectangle in [[-1, 0, 2, 2], [1, 1, 1, 4], [1., 1, 4, 4], [1, 1, 7, 4]]:
            with self.assertRaises(ValueError): cap.append_skin_patch(doc, blob, rectangle)
        for mutate in [lambda d: d['meshes'][0]['primitives'][1].update(material=0),
                       lambda d: d['materials'][0]['pbrMetallicRoughness']['baseColorTexture'].update(texCoord=1),
                       lambda d: d['materials'][0]['pbrMetallicRoughness']['baseColorTexture'].update(extensions={'KHR_texture_transform': {}}),
                       lambda d: d['materials'][0].update(extensions={'KHR_materials_unlit': {}})]:
            bad = copy.deepcopy(doc); mutate(bad)
            with self.assertRaises(ValueError): cap.append_skin_patch(bad, blob, [1, 1, 4, 4])
        child, data, _ = cap.append_skin_patch(doc, blob, [1, 1, 4, 4])
        with self.assertRaises(ValueError): cap.append_skin_patch(child, data, [1, 1, 4, 4])

    def test_working_contract_once_and_explicit_trial_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            tp = Path(directory)/'target.json'; target = target_fixture()
            target['rig'].update(pilotAccepted=True, offlineStructureAccepted=True, pilotAcceptanceScope='offline-rig-structure')
            tp.write_text(json.dumps(target)); c = {**tc.binding(tp, target, 'working'), 'schemaVersion': 1,
                'kind': 'root-pinned-pelvis-cap-skin-C3-material-configuration', 'scope': cap.SCOPE,
                'part': 'pelvis', 'coordinateSpace': 'working', 'statureApplications': 0,
                'sourcePixelRectangle': cap.RECTANGLE, 'candidateID': 'C', 'capPrimitives': [1, 2], 'sourceBodyPrimitive': 0,
                'capNormalMapAbsent': True, 'addedAO': 0., 'bodyNormalStrengthPreserved': 1.,
                'allBodyUVMapsAndOpaqueUnderwearPreserved': True, 'allCapPNTWUVIndicesPreserved': True,
                'pendingGates': {k: False for k in cap.PENDING}, 'expectedExecutor': cap.pin(cap.__file__)}
            cap.validate_configuration(c, tp, target)
            for key, value in [('coordinateSpace', 'runtime'), ('statureApplications', 1), ('scope', 'production'),
                ('candidateID', 'A'), ('sourcePixelRectangle', [760, 98, 764, 101]), ('addedAO', .15),
                ('capNormalMapAbsent', False), ('bodyNormalStrengthPreserved', .5), ('materialAccepted', True)]:
                bad = copy.deepcopy(c); bad[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError): cap.validate_configuration(bad, tp, target)
            bad = copy.deepcopy(c); bad['expectedExecutor']['sha256'] = '0'*64
            with self.assertRaises(ValueError): cap.validate_configuration(bad, tp, target)
            for scope in ['offline-rig-structure-only', 'rigStructureOffline', None]:
                badtarget = copy.deepcopy(target); badtarget['rig']['pilotAcceptanceScope'] = scope
                with self.assertRaises(ValueError): cap.validate_configuration(c, tp, badtarget)

    def test_durable_semantic_ownership_is_not_material_or_connector_acceptance(self):
        ownership = {'schemaVersion': 1, 'kind': 'root-reviewed-selected-pelvis15-skin-cap-ownership', 'reviewedBy': '/root',
                     'semanticCapOwnershipAccepted': True, 'capPrimitives': [1, 2], 'role': 'skin', 'selectedDiagnosticPatch': 'C',
                     'sourcePixelRectangle': cap.RECTANGLE, 'actualMaterialExportAccepted': False,
                     'boundaryEvidence': {'sha256': cap.EVIDENCE_SHA['skinBoundaryEvidence']}, 'proposal': {'sha256': cap.EVIDENCE_SHA['patchProposal']}}
        shape = {'schemaVersion': 1, 'kind': 'human-approved-shin90-foot120-shapes', **{k: True for k in
                 ['shinGirthAndLengthFrozen', 'foot120SizeAndNonconnectorShapeFrozen', 'bonePositionsAndLimbLengthsProtected',
                  'soleToesUVMapsMaterialsProtected', 'noNewShelvesRuleRetained']}}
        cap.validate_authorities(ownership, shape)
        for key, value in [('reviewedBy', 'worker'), ('role', 'garment'), ('selectedDiagnosticPatch', 'B'),
                           ('actualMaterialExportAccepted', True), ('materialAccepted', True)]:
            bad = copy.deepcopy(ownership); bad[key] = value
            with self.assertRaises(ValueError): cap.validate_authorities(bad, shape)
        bad = copy.deepcopy(shape); bad['connectorAccepted'] = True
        with self.assertRaises(ValueError): cap.validate_authorities(ownership, bad)

    def test_descendant_rejects_relabel_coercion_and_final_scope(self):
        r = {'operation': 'append-exact-C3-RGBA-ORM-skin-cap-material-only', 'part': 'pelvis', 'joint': 'pelvis_g',
             'primitiveRoleStatus': copy.deepcopy(cap.ROLES), 'skinOwnershipReviewedByRoot': True,
             'canonicalNativeLineage': False, 'diagnosticOnly': True, 'closedExteriorClaim': False,
             'geometryAttributesAndArchivesUnchanged': True}
        cap.validate_descendant_metadata(r)
        for key, value in [('canonicalNativeLineage', True), ('diagnosticOnly', False), ('geometryAccepted', True),
                           ('closedExteriorClaim', True), ('joint', 'torso_g')]:
            bad = copy.deepcopy(r); bad[key] = value
            with self.assertRaises(ValueError): cap.validate_descendant_metadata(bad)
        bad = copy.deepcopy(r); bad['primitiveRoleStatus']['3'] = 'skin'
        with self.assertRaises(ValueError): cap.validate_descendant_metadata(bad)


if __name__ == '__main__': unittest.main()
