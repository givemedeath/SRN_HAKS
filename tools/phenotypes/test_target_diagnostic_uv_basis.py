"""Focused opt-in UV-basis semantics and original/cap storage preservation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import target_diagnostic_material_lineage as lineage
import target_diagnostic_uv_basis as policy
from partition_target_pelvis_materials import active_faces, face_layout_sha
from place_purposebuilt_pelvis import BASIS, accessor, rotation_xyz
from segment_target_diagnostic_pelvis_body import subdivide_body as strict_subdivide
from segment_target_diagnostic_pelvis_uv_basis import execute, subdivide_body
from segment_target_pelvis_boundary import CORNER_KEYS, new_corner as strict_corner
from test_segment_target_diagnostic_pelvis_body import fixture, selection


def plane_parent():
    p = np.asarray([[[0, 0, 0], [2, 0, 0], [0, 3, 0]]], dtype=float)
    uv = np.asarray([[[0, 0], [1, 0], [0, 1]]], dtype=float)
    n = np.tile([0., 0., 1.3], (1, 3, 1))
    t = np.tile([0., 1.7, 0., -1.], (1, 3, 1))
    t[0, 1, 3] = 1.
    native = uv.copy(); native[:, :, 1] = 1 - native[:, :, 1]
    return {'positions': p, 'sourcePositions': p.copy(), 'normals': n,
            'sourceNormals': n.copy(), 'uvGltf': uv, 'uvNative': native,
            'sourceUVNative': native.copy(), 'tangents': t}


def canonical_point(parent, weights):
    active = np.flatnonzero(weights)
    keys = [tuple(p) for p in parent['positions'][0]]
    lo, hi = sorted(active, key=lambda i: keys[i])
    return {((keys[lo], keys[hi]), float(weights[hi])): weights @ parent['positions'][0]}


def uv_selection(doc, blob, ids):
    value = selection(doc, blob, ids)
    value['kind'] = policy.MAP_KIND
    value['newCornerShadingPolicy'] = policy.POLICY_ID
    value['rootReview']['newCornerShadingPolicy'] = policy.POLICY_ID
    return value


def oriented_fixture():
    """A tetrahedron with genuine per-face UV/N basis and literal old corners."""
    doc, blob, body, caps, ids = fixture()
    data = bytearray(blob)
    normals = []; tangents = []
    for f, p in enumerate(body['positions']):
        n = np.cross(p[1]-p[0], p[2]-p[0]); n /= np.linalg.norm(n)
        temp = copy.deepcopy(body); temp['normals'][f] = np.tile(n, (3, 1))
        t, _ = policy.basis_details(temp, f, [1, 0, 0])
        # Authored T deliberately differs from the UV derivative and is nonunit.
        rotated = (np.cos(.17)*t[:3] + np.sin(.17)*np.cross(n, t[:3]))*1.2
        normals.append(np.tile(n*1.3, (3, 1)))
        ts = np.tile(np.r_[rotated, t[3]], (3, 1))
        if f == 0: ts[1, 3] *= -1
        tangents.append(ts)
    body['normals'] = np.asarray(normals, dtype=float)
    body['sourceNormals'] = body['normals'].copy()
    body['tangents'] = np.asarray(tangents, dtype=float)
    def append(value, kind):
        value = np.asarray(value); data.extend(b'\0'*(-len(data)%4))
        offset = len(data); data.extend(value.tobytes()); data.extend(b'\0'*(-len(data)%4))
        doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':value.nbytes})
        doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,
                                'componentType':5126 if value.dtype.kind=='f' else 5125,
                                'count':len(value),'type':kind})
        return len(doc['accessors'])-1
    attrs = {
        'POSITION': (body['positions']@BASIS).reshape(-1, 3),
        'NORMAL': (body['normals']@BASIS).reshape(-1, 3),
        'TEXCOORD_0': body['uvGltf'].reshape(-1, 2),
        'TANGENT': np.concatenate((body['tangents'][:,:,:3]@BASIS,
                                  body['tangents'][:,:,3:]), axis=2).reshape(-1, 4)}
    indices = np.arange(12, dtype='<u4')
    primitive = doc['meshes'][0]['primitives'][0]
    for semantic, rows in attrs.items():
        extra = rows[:1].copy()
        if semantic == 'NORMAL': extra[0] = [0, 0, 1e-13]
        primitive['attributes'][semantic] = append(np.concatenate((rows, extra)).astype('<f4'),
                                                  'VEC'+str(rows.shape[1]))
    primitive['indices'] = append(indices, 'SCALAR')
    doc['buffers'][0]['byteLength'] = len(data)
    return doc, bytes(data), body, caps, ids


class DiagnosticUvBasisTests(unittest.TestCase):
    def test_raw_uv_derivatives_proper_basis_rotation_scale_and_v_sign(self):
        parent = plane_parent(); w = np.asarray([.2, .8, 0])
        derived, corner = policy.new_corner(parent, 0, w, canonical_point(parent, w), policy=policy.POLICY_ID)
        self.assertEqual(corner, -1)
        np.testing.assert_allclose(derived['tangents'], [1, 0, 0, 1], atol=1e-14)
        np.testing.assert_allclose(derived['normals'], [0, 0, 1], atol=1e-14)
        self.assertEqual(derived['uvNative'][1], 1-derived['uvGltf'][1])
        with self.assertRaisesRegex(ValueError, 'handedness'):
            strict_corner(parent, 0, w, canonical_point(parent, w))
        for R in (BASIS, rotation_xyz([31, -17, 64])):
            shifted = copy.deepcopy(parent)
            for key in ('positions', 'sourcePositions'): shifted[key] = parent[key]@R.T*1.41+[.1, -.2, .3]
            for key in ('normals', 'sourceNormals'): shifted[key] = parent[key]@R.T
            shifted['tangents'][:,:,:3] = parent['tangents'][:,:,:3]@R.T
            new, _ = policy.new_corner(shifted, 0, w, canonical_point(shifted, w), policy=policy.POLICY_ID)
            np.testing.assert_allclose(new['tangents'][:3], derived['tangents'][:3]@R.T, atol=1e-14)
            self.assertEqual(new['tangents'][3], 1)
            np.testing.assert_allclose(new['positions'], derived['positions']@R.T*1.41+[.1,-.2,.3], atol=1e-14)
        vflip = copy.deepcopy(parent); vflip['uvGltf'][:,:,1] = 1-vflip['uvGltf'][:,:,1]
        changed, _ = policy.new_corner(vflip, 0, w, canonical_point(vflip, w), policy=policy.POLICY_ID)
        np.testing.assert_allclose(changed['tangents'], [1, 0, 0, -1], atol=1e-14)

    def test_uv_u_flip_changes_tangent_and_sign_without_position_change(self):
        parent = plane_parent(); w = np.asarray([.6, 0, .4])
        parent['uvGltf'][:,:,0] = 1-parent['uvGltf'][:,:,0]
        new, _ = policy.new_corner(parent, 0, w, canonical_point(parent,w), policy=policy.POLICY_ID)
        np.testing.assert_allclose(new['tangents'], [-1,0,0,-1], atol=1e-14)
        np.testing.assert_allclose(new['positions'], w@parent['positions'][0], atol=0)

    def test_one_hot_original_corner_is_literal_even_for_singular_uv(self):
        parent = plane_parent(); parent['uvGltf'][:] = 0
        for c in range(3):
            new, corner = policy.new_corner(parent, 0, np.eye(3)[c], {}, policy=policy.POLICY_ID)
            self.assertEqual(corner, c)
            for key in CORNER_KEYS|{'tangents'}:
                self.assertEqual(new[key].tobytes(), parent[key][0,c].tobytes())
        with self.assertRaisesRegex(ValueError, 'one-hot'):
            policy.new_corner(parent,0,[1,1e-13,0],{},policy=policy.POLICY_ID)
        with self.assertRaisesRegex(ValueError,'edge cut'):
            policy.new_corner(parent,0,[.2,.3,.5],{},policy=policy.POLICY_ID)

    def test_singular_uv_normal_projected_tangent_and_orientation_rejected(self):
        w = np.asarray([.5,.5,0])
        for change, message in [('uv','raw-UV'),('nearuv','raw-UV'),('nan','Finite'),
                                ('normal','normal'),('source-normal','normal'),
                                ('tangent','projected UV tangent'),('orientation','orientation')]:
            parent = plane_parent()
            if change=='uv': parent['uvGltf'][0,2]=[2,0]
            elif change=='nearuv':parent['uvGltf'][0,2]=[2,1e-14]
            elif change=='nan':parent['positions'][0,2,0]=np.nan
            elif change=='normal':parent['normals'][0,0]=[0,0,1];parent['normals'][0,1]=[0,0,-1]
            elif change=='source-normal':parent['sourceNormals'][:]=0
            elif change=='tangent':parent['normals'][:]=[1,0,0]
            else:parent['normals'][:]=[0,1,0]
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,message):
                policy.new_corner(parent,0,w,canonical_point(parent,w),policy=policy.POLICY_ID)

    def test_distinct_map_rootreview_config_policy_required_and_old_guard_preserved(self):
        doc,blob,body,caps,ids=oriented_fixture();valid=uv_selection(doc,blob,ids)
        for change in ('map-kind','no-policy','wrong-policy','review-policy','no-review','unknown'):
            bad=copy.deepcopy(valid)
            if change=='map-kind':bad['kind']=lineage.MAP_KIND
            elif change=='no-policy':bad.pop('newCornerShadingPolicy')
            elif change=='wrong-policy':bad['newCornerShadingPolicy']='authored-default'
            elif change=='review-policy':bad['rootReview']['newCornerShadingPolicy']='other'
            elif change=='no-review':bad['rootReview']['reviewed']=False
            else:bad['normalRewrite']=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                subdivide_body(doc,blob,body,caps,ids,bad)
        with self.assertRaises(ValueError):strict_subdivide(doc,blob,body,caps,ids,valid)
        strict_map=selection(doc,blob,ids)
        with self.assertRaisesRegex(ValueError,'handedness'):strict_subdivide(doc,blob,body,caps,ids,strict_map)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for kind,value in [(policy.CONFIG_KIND,None),(policy.CONFIG_KIND,'wrong'),('target-diagnostic-pelvis-body-segmentation',policy.POLICY_ID)]:
                path=root/'config.json';path.write_text(json.dumps({'schemaVersion':2,'kind':kind,'diagnosticOnly':True,'coordinateSpace':'working','part':'pelvis','newCornerShadingPolicy':value}))
                with self.subTest(kind=kind,value=value),self.assertRaises(ValueError):execute(path,root/'unused')
                self.assertFalse((root/'unused').exists())

    def test_append_only_mixed_source_sign_trial_preserves_originals_caps_maps_and_ancestry(self):
        doc,blob,body,caps,ids=oriented_fixture();saved=copy.deepcopy(doc)
        new,binary,archive,newcaps,proof=subdivide_body(doc,blob,body,caps,ids,uv_selection(doc,blob,ids))
        self.assertEqual(doc,saved);self.assertEqual(binary[:len(blob)],blob)
        lineage.verify_unchanged_storage(new,binary,doc,blob)
        self.assertEqual(new['materials'],doc['materials']+[doc['materials'][0]])
        for key in caps:self.assertEqual(newcaps[key].tobytes(),caps[key].tobytes())
        oldnormal=doc['meshes'][0]['primitives'][0]['attributes']['NORMAL']
        self.assertEqual(accessor(new,binary,oldnormal)[-1].tobytes(),accessor(doc,blob,oldnormal)[-1].tobytes())
        for out,f in enumerate(archive['parentBodyFaceIds']):
            np.testing.assert_allclose(archive['positions'][out],archive['parentBodyCornerBarycentrics'][out]@body['positions'][f],atol=1e-16)
            np.testing.assert_allclose(archive['uvGltf'][out],archive['parentBodyCornerBarycentrics'][out]@body['uvGltf'][f],atol=1e-16)
            for c,old in enumerate(archive['sourceCornerOrder'][out]):
                if old>=0:
                    for key in CORNER_KEYS|{'tangents'}:self.assertEqual(archive[key][out,c].tobytes(),body[key][f,old].tobytes())
                else:
                    T=archive['tangents'][out,c];N=archive['normals'][out,c]
                    self.assertAlmostEqual(np.linalg.norm(T[:3]),1,places=13);self.assertAlmostEqual(T[:3]@N,0,places=13)
        self.assertEqual(proof['bodyTrianglesAfter'],10);self.assertEqual(proof['statureApplicationsAdded'],0)
        summary=proof['newCornerShadingEvidence']
        self.assertEqual(summary['originalStrictAuthoredHandednessRejectedFaces'],1)
        self.assertFalse(summary['authoredTangentsPreservedAtNewCorners'])
        self.assertTrue(summary['authoredTangentsPreservedAtOriginalCorners'])
        self.assertEqual(proof['capPrimitiveIdsUnchanged'],[1,2])
        self.assertLess(proof['maximumAreaFractionError'],1e-12);self.assertLess(proof['maximumPlaneDeviationMetres'],1e-14)

    def test_whole_faces_keep_unusable_authored_uv_and_nonunit_basis_untouched(self):
        doc,blob,body,caps,ids=oriented_fixture();value=uv_selection(doc,blob,ids)
        value.update(cutFaces=[],wholeSkinParentBodyFaceIds=[0,1,2],wholeGarmentParentBodyFaceIds=[3])
        new,binary,archive,_,proof=subdivide_body(doc,blob,body,caps,ids,value)
        for key in CORNER_KEYS|{'tangents'}:self.assertEqual(archive[key].tobytes(),body[key].tobytes())
        self.assertEqual(proof['newCornerShadingEvidence']['uniqueNewCornersChecked'],0)
        self.assertEqual(proof['bodyTrianglesAfter'],4)


if __name__=='__main__':unittest.main()
