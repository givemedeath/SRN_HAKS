"""Focused target/resource/loop/palette guards for additive native preview."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as c
import test_audit_target_native_part as native_fixture
import test_human_female_stock_exact as female_fixture
import prepare_target_native_material_preview as preview


def put_name(data, at, width, name):
    blob = name.encode()+b'\0'
    data[at:at+width] = blob+bytes(width-len(blob))


def stock_native():
    data, _, _, nodes, raw = native_fixture.fixture(('skin',))
    model = 'pfh0_neck001'; at = 12+nodes[0]
    put_name(data, 20, 64, model)
    root = struct.unpack_from('<I', data, 12+0x48)[0]
    put_name(data, 12+root+32, 32, model)
    put_name(data, at+32, 32, model+'g')
    put_name(data, at+0xe8, 64, model); put_name(data, at+0xe8+3*64, 64, '')
    struct.pack_into('<fff', data, at+0xac, 1, 1, 1)
    struct.pack_into('<fff', data, at+0xb8, 1, 1, 1)
    struct.pack_into('<I', data, at+0xdc, 1)
    t = struct.unpack_from('<I', data, at+0x258)[0]
    struct.pack_into('<I', data, at+0x248, t)
    struct.pack_into('<III', data, 12+raw+t, 0xffffffff, 0xffffffff, 0xffffffff)
    struct.pack_into('<I', data, at+0x258, 0xffffffff)
    struct.pack_into('<I', data, at+0x260, 0xffffffff)
    return data, at, raw


def file_pin(path):
    return {'path': str(path.resolve()), 'sha256': c.sha(path)}


class NativePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.tp, self.target = female_fixture.stock_fixture(self.root)
        data, _, _ = stock_native()
        self.model = self.root/'pfh0_neck001.mdl'; self.model.write_bytes(data)
        self.plt = self.root/'pfh0_neck001.plt'
        pixels = np.asarray([[[0, 0], [255, 0]], [[68, 0], [98, 0]]], dtype='u1')
        self.plt.write_bytes(b'PLT V1  '+struct.pack('<IIII', 10, 0, 2, 2)+pixels[::-1].tobytes())
        self.palette = self.root/'pal_skin01.tga'
        palette = np.zeros((10, 256, 3), dtype='u1')
        palette[3] = np.arange(256, dtype='u1')[:, None]
        palette[8] = np.clip(np.arange(256)[:, None]*.75, 0, 255).astype('u1')
        Image.fromarray(palette).save(self.palette)
        self.inventory = self.root/'baseline.json'
        self.inventory.write_text(json.dumps({'resources': [{'name': p.name, 'sha256': c.sha(p)} for p in
                (self.model, self.plt, self.palette)]}), encoding='utf-8')
        self.target['frozenInputs'] = {str(p): c.sha(p) for p in (self.model, self.plt, self.palette, self.inventory)}
        self.tp.write_text(json.dumps(self.target), encoding='utf-8')
        self.cfg = {'schemaVersion': 1, 'kind': 'target-native-material-preview-inputs', 'diagnosticOnly': True,
                    'targetContract': file_pin(self.tp), 'coordinateSpace': 'working',
                    'stockInventory': file_pin(self.inventory), 'skinPalette': file_pin(self.palette),
                    'paletteRows': [3, 8], 'parts': {'neck': {'kind': 'installed-stock-neck',
                    'binding': c.binding(self.tp, self.target, 'working'), 'nativeModel': file_pin(self.model), 'plt': file_pin(self.plt)}},
                    'poses': [{'id': 'stock-bind'}], 'render': {'width': 256, 'height': 256,
                    'modes': ['emission-only-color', 'neutral-native-material'], 'views': list(preview.VIEWS),
                    'focusParts': ['neck'], 'padding': 1.18}}

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, config=None, name='prepared'):
        path = self.root/(name+'.json')
        path.write_text(json.dumps(config or self.cfg), encoding='utf-8')
        return preview.prepare(path, self.root/name)

    def test_installed_native_arrays_and_missing_tangents_preserved(self):
        before = c.sha(self.model)
        path = self.prepare(); receipt = json.loads(path.read_text())
        row = receipt['parts']['neck'][0]
        self.assertEqual(row['arrays']['missingNativeArrays'], ['tangent', 'sign'])
        with np.load(row['arrays']['path']) as archive:
            native = preview.stock_neck_decode(self.model.read_bytes(), 'pfh0_neck001')[0]['pfh0_neck001g']
            for key in archive.files:
                np.testing.assert_array_equal(archive[key], native[key])
                self.assertEqual(archive[key].dtype, native[key].dtype)
        self.assertEqual(c.sha(self.model), before)
        self.assertFalse(receipt['clientAccepted'])
        self.assertFalse(receipt['nativeCompilerExecuted'])
        self.assertEqual(set(receipt['parts']), {'neck'})

    def test_changed_gender_target_identity_and_palette_rejected(self):
        for key, value in [('gender', 'male'), ('prefix', 'pmh0'), ('phenotype', 1), ('raceId', 7), ('appearanceRow', 7)]:
            bad = copy.deepcopy(self.target); bad['identity'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                preview.validate_identity(bad)
        for rows in ([3], [8, 3], [3, 8, 8], [True, 8], [3, 176]):
            bad = copy.deepcopy(self.cfg); bad['paletteRows'] = rows
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                preview.controls(bad)

    def test_stale_pinned_input_and_cross_target_bindings_rejected_before_outputs(self):
        self.plt.write_bytes(self.plt.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError, 'Target input changed'):
            self.prepare(name='stale')
        self.assertFalse((self.root/'stale').exists())
        self.setUp_fresh_files_for_binding()

    def setUp_fresh_files_for_binding(self):
        # Separate state restore; do not hide the first failed output.
        self.plt.write_bytes(self.plt.read_bytes()[:-1])
        for field, value in [('targetId', 'other-target'), ('rigRevision', 'other-rig'),
                              ('coordinateSpace', 'runtime'), ('targetContractSha256', '0'*64)]:
            bad = copy.deepcopy(self.cfg); bad['parts']['neck']['binding'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'another target'):
                self.prepare(bad, 'cross-'+field.lower())

    def test_resource_owner_inventory_and_unresolved_garment_kinds_rejected(self):
        for part in ('head', 'bogus', 'chest'):
            bad = copy.deepcopy(self.cfg); bad['parts'] = {part: bad['parts']['neck']}
            with self.subTest(part=part), self.assertRaises(ValueError):
                preview.controls(bad)
        bad = copy.deepcopy(self.cfg); bad['parts']['neck']['kind'] = 'unreviewed-garment-proposal'
        with self.assertRaises(ValueError):
            preview.controls(bad)
        bad = copy.deepcopy(self.cfg); bad['parts']['neck']['binding']['part'] = 'pelvis'
        # Extra arbitrary data is not a substitute for ownership; top-level part
        # and model identity are authoritative and still verified.
        bad['parts']['neck']['nativeModel']['path'] = str(self.root/'pfh0_pelvis001.mdl')
        with self.assertRaises(ValueError):
            self.prepare(bad, 'foreign-model')

    def test_stock_decoder_rejects_nonwhite_colors_missing_normals_and_nested_tree(self):
        for mutation in ('colors', 'normals', 'bounds', 'nested', 'render'):
            data, at, raw = stock_native()
            if mutation == 'colors':
                ptr = struct.unpack_from('<I', data, at+0x248)[0]
                struct.pack_into('<I', data, 12+raw+ptr, 0xffeeeeee)
            elif mutation == 'normals':
                struct.pack_into('<I', data, at+0x244, 0xffffffff)
            elif mutation == 'bounds':
                struct.pack_into('<I', data, at+0x244, 0xfffffffe)
            elif mutation == 'nested':
                struct.pack_into('<III', data, at+0x48, 344, 1, 1)
            else:
                struct.pack_into('<I', data, at+0xdc, 0)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                preview.stock_neck_decode(data, 'pfh0_neck001')

    def test_palette_lookup_before_filter_is_not_lookup_of_interpolated_shade(self):
        palette = np.zeros((10, 256, 3), dtype='u1'); palette[3, 255] = 255; palette[3, 128] = 12
        plt = b'PLT V1  '+struct.pack('<IIII', 10, 0, 2, 1)+bytes([0, 0, 255, 0])
        from offline_native_material_bridge import palette_rgba
        rgba = palette_rgba(plt, palette, 3)
        from audit_target_joint_bands import sample_pixels
        actual = sample_pixels(rgba[..., :3], np.asarray([[.5, .5]]), 33071, 33071)
        np.testing.assert_allclose(actual, [[127.5, 127.5, 127.5]])
        self.assertNotEqual(actual[0, 0], palette[3, 128, 0])

    def test_actual_loop_custom_normals_and_native_tangent_signs_must_remain_effective(self):
        data, model, names, _, _ = native_fixture.fixture(('skin',))
        native = next(iter(native_fixture.decode(data, model, names)[0].values()))
        native['normal'] = np.tile(np.asarray([0, .6, .8], dtype='<f4'), (3, 1))
        idx = native['faces'].reshape(-1); attrs = {key: native[key].copy() for key in ('normal', 'tangent', 'sign')}
        proof = preview.verify_loop_representation(native, idx, native['position'][idx], native['normal'][idx],
                                                   native['uv'][idx], attrs)
        self.assertEqual(proof['actualCustomLoopNormalDirectionMaximumComponentError'], 0)
        with self.assertRaisesRegex(ValueError, 'ineffective'):
            preview.verify_loop_representation(native, idx, native['position'][idx], np.tile([0, 0, 1], (3, 1)),
                                               native['uv'][idx], attrs)
        attrs['sign'][0] *= -1
        with self.assertRaisesRegex(ValueError, 'attributes changed'):
            preview.verify_loop_representation(native, idx, native['position'][idx], native['normal'][idx],
                                               native['uv'][idx], attrs)

    def candidate(self, part):
        roles = ('garment', 'skin') if part in ('chest', 'pelvis') else ('skin',)
        data, _, _, nodes, _ = native_fixture.fixture(roles)
        model = c.model(self.target, part)
        put_name(data, 20, 64, model)
        root = struct.unpack_from('<I', data, 12+0x48)[0]
        put_name(data, 12+root+32, 32, model)
        names = []
        for index, (off, role) in enumerate(zip(nodes, roles)):
            name = model+'p'+str(index); names.append(name)
            put_name(data, 12+off+32, 32, name)
            material = model+('f' if role == 'garment' else '')
            put_name(data, 12+off+0xe8, 64, material)
            put_name(data, 12+off+0xe8+3*64, 64, material)
        folder = self.root/('candidate-'+part); folder.mkdir()
        native = folder/(model+'.mdl'); native.write_bytes(data)
        material_hashes = {}
        for role in roles:
            material = model+('f' if role == 'garment' else '')
            normal = folder/(material+'n.tga'); rough = folder/(material+'r.tga')
            Image.fromarray(np.full((2, 2, 3), [128, 128, 255], dtype='u1')).save(normal)
            Image.fromarray(np.full((2, 2, 3), 127, dtype='u1')).save(rough)
            mtr = folder/(material+'.mtr')
            text = 'renderhint NormalTangents\ntexture1 '+material+'n\ntexture3 '+material+'r\n'
            if role == 'garment':
                color = folder/(material+'.tga'); Image.fromarray(np.full((2, 2, 3), 32, dtype='u1')).save(color)
                text += 'texture0 '+material+'\n'
            else:
                color = folder/(material+'.plt'); color.write_bytes(self.plt.read_bytes())
            mtr.write_text(text+'parameter float Roughness 0\nparameter float Specularity .04\nparameter float Metallicness .001\n')
            material_hashes.update({p.name: c.sha(p) for p in (normal, rough, color, mtr)})
        binding = c.binding(self.tp, self.target, 'working')
        stage = folder/'target-stage.json'
        stage.write_text(json.dumps({'schemaVersion': 2, 'kind': 'target-part-stage', **binding,
                         'part': part, 'model': model, 'materialRoles': {str(i): role for i, role in enumerate(roles)},
                         'materialResourceHashes': material_hashes, 'sourceSha256': '0'*64, 'sourceReceiptSha256': '1'*64}))
        meshes, root_record = native_fixture.decode(data, model, names)
        audit = folder/'native-audit.json'
        audit.write_text(json.dumps({'schemaVersion': 2, 'kind': 'target-native-part-audit', **binding,
            'part': part, 'model': model, 'nativeModelSha256': c.sha(native), 'stageReceipt': str(stage),
            'stageReceiptSha256': c.sha(stage), 'attributeTransportVerified': True, 'materialTransportVerified': True,
            'meshes': {name: {'role': role, 'nativeLayout': meshes[name]['layout']} for name, role in zip(names, roles)},
            'frozenInputs': {str(p): c.sha(p) for p in folder.iterdir() if p.is_file()}}))
        return {'kind': 'audited-candidate', 'binding': binding, 'nativeModel': file_pin(native), 'nativeAudit': file_pin(audit)}

    def test_arbitrary_declared_fourteen_part_native_inventory_preserves_every_pnut_archive(self):
        cfg = copy.deepcopy(self.cfg)
        for part in sorted(c.BODY_PARTS):
            cfg['parts'][part] = self.candidate(part)
        cfg['render']['focusParts'] = sorted(cfg['parts'])
        path = self.prepare(cfg, 'complete-declared-test-inventory')
        result = json.loads(path.read_text())
        self.assertEqual(set(result['parts']), c.BODY_PARTS | {'neck'})
        for part in c.BODY_PARTS:
            row = result['parts'][part][0]
            self.assertEqual(row['arrays']['missingNativeArrays'], [])
            meshes = native_fixture.decode(Path(cfg['parts'][part]['nativeModel']['path']).read_bytes(),
                                            c.model(self.target, part), [r['name'] for r in result['parts'][part]])[0]
            for record in result['parts'][part]:
                with np.load(record['arrays']['path']) as archive:
                    for key in preview.KEYS:
                        np.testing.assert_array_equal(archive[key], meshes[record['name']][key])
        self.assertFalse(result['nativeCompilerExecuted'])

    def test_candidate_audit_binding_and_material_changes_fail_before_output(self):
        cfg = copy.deepcopy(self.cfg); entry = self.candidate('bicepl'); cfg['parts']['bicepl'] = entry
        audit_path = Path(entry['nativeAudit']['path']); audit = json.loads(audit_path.read_text())
        audit['targetId'] = 'foreign-female'; audit_path.write_text(json.dumps(audit))
        entry['nativeAudit'] = file_pin(audit_path)
        with self.assertRaisesRegex(ValueError, 'another target'):
            self.prepare(cfg, 'candidate-cross')
        audit['targetId'] = self.target['id']; audit_path.write_text(json.dumps(audit)); entry['nativeAudit'] = file_pin(audit_path)
        (Path(entry['nativeModel']['path']).parent/'pfh0_bicepl001n.tga').write_bytes(b'wrong-normal-pixels')
        with self.assertRaisesRegex(ValueError, 'Changed preview input'):
            self.prepare(cfg, 'candidate-stale-material')


    def test_projection_preserves_common_magnification_and_rigid_camera_basis(self):
        native = preview.stock_neck_decode(self.model.read_bytes(), 'pfh0_neck001')[0]['pfh0_neck001g']
        plans = preview.cameras(native['position'], self.cfg['render'])
        self.assertEqual(len(set(row['orthographicHeightMetres'] for row in plans)), 1)
        for row in plans:
            rotation = np.asarray(row['matrixWorld'])[:3, :3]
            np.testing.assert_array_equal(rotation.T@rotation, np.eye(3))
            self.assertEqual(np.linalg.det(rotation), 1)


if __name__ == '__main__':
    unittest.main()

