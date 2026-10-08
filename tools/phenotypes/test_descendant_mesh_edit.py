import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from descendant_mesh_edit import (Mesh, Descendant, closure, mirror_descendant, mirror_corner_map, write_preview,
                                  preview_corners, descendant_preview, transported_positions, laplacian_smooth)
from place_purposebuilt_pelvis import BASIS

PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010806000000'
                    '1f15c4890000000d49444154789c6360000000000500010d0a2db40000000049454e44ae426082')


def write_test_glb(path, pos, faces, uv=None, nrm=None, tangent=False):
    """Indexed single-primitive GLB (NWN coordinates in, glTF stored) with one embedded PNG material."""
    pos = np.asarray(pos, float); faces = np.asarray(faces, np.uint32)
    if nrm is None:
        acc = np.zeros_like(pos)
        fn = np.cross(pos[faces[:, 1]] - pos[faces[:, 0]], pos[faces[:, 2]] - pos[faces[:, 0]])
        for k in range(3):
            np.add.at(acc, faces[:, k], fn)
        nrm = acc / np.maximum(np.linalg.norm(acc, axis=1), 1e-12)[:, None]
    if uv is None:
        uv = np.c_[(np.arctan2(pos[:, 1], pos[:, 0]) / (2 * np.pi)) % 1, pos[:, 2] - pos[:, 2].min()]
    chunks = [(pos @ BASIS).astype('<f4'), (np.asarray(nrm) @ BASIS).astype('<f4'), np.asarray(uv).astype('<f4')]
    if tangent:
        t = np.c_[np.cross(np.asarray(nrm), [0, 0, 1.]) + [1e-3, 0, 0], np.ones(len(pos))]
        t[:, :3] /= np.linalg.norm(t[:, :3], axis=1)[:, None]
        t[:, :3] = t[:, :3] @ BASIS
        chunks.append(t.astype('<f4'))
    chunks.append(faces.reshape(-1).astype('<u4'))
    binary = bytearray(); views = []; accessors = []
    types = ['VEC3', 'VEC3', 'VEC2'] + (['VEC4'] if tangent else []) + ['SCALAR']
    for data, typ in zip(chunks, types):
        binary.extend(b'\0' * (-len(binary) % 4)); off = len(binary); binary.extend(data.tobytes())
        views.append({'buffer': 0, 'byteOffset': off, 'byteLength': data.nbytes})
        item = {'bufferView': len(views) - 1, 'componentType': 5126 if data.dtype.kind == 'f' else 5125,
                'count': len(data) if data.ndim > 1 else len(data), 'type': typ}
        if len(accessors) == 0:
            item.update(min=data.min(0).tolist(), max=data.max(0).tolist())
        accessors.append(item)
    binary.extend(b'\0' * (-len(binary) % 4)); off = len(binary); binary.extend(PNG)
    views.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(PNG)})
    binary.extend(b'\0' * (-len(binary) % 4))
    attrs = {'POSITION': 0, 'NORMAL': 1, 'TEXCOORD_0': 2}
    if tangent:
        attrs['TANGENT'] = 3
    doc = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
           'meshes': [{'primitives': [{'attributes': attrs, 'indices': len(accessors) - 1, 'material': 0}]}],
           'materials': [{'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}}], 'textures': [{'source': 0}],
           'images': [{'bufferView': len(views) - 1, 'mimeType': 'image/png'}], 'accessors': accessors, 'bufferViews': views,
           'buffers': [{'byteLength': len(binary)}]}
    text = json.dumps(doc).encode(); text += b' ' * (-len(text) % 4)
    Path(path).write_bytes(struct.pack('<III', 0x46546c67, 2, 28 + len(text) + len(binary)) + struct.pack('<II', len(text), 0x4e4f534a)
                           + text + struct.pack('<II', len(binary), 0x004e4942) + bytes(binary))


def capped_cylinder(radius=1.0, height=2.0, rings=12, segments=24, z0=0.0, x0=0.0):
    pos = []; faces = []
    for i in range(rings + 1):
        z = z0 + height * i / rings
        for j in range(segments):
            a = 2 * np.pi * j / segments
            pos.append([x0 + radius * np.cos(a), radius * np.sin(a), z])
    bottom = len(pos); pos.append([x0, 0, z0]); top = len(pos); pos.append([x0, 0, z0 + height])
    for i in range(rings):
        for j in range(segments):
            a = i * segments + j; b = i * segments + (j + 1) % segments
            c = a + segments; d = b + segments
            faces += [[a, b, d], [a, d, c]]
    for j in range(segments):
        faces.append([bottom, (j + 1) % segments, j])
        faces.append([top, rings * segments + j, rings * segments + (j + 1) % segments])
    return np.asarray(pos), np.asarray(faces)


class DescendantMeshEditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_identity_and_displacement_preserve_uv_maps(self):
        pos, faces = capped_cylinder()
        write_test_glb(self.dir / 'm.glb', pos, faces, tangent=True)
        mesh = Mesh(self.dir / 'm.glb')
        self.assertEqual(closure(mesh.F)['boundaryEdges'], 0)
        d = Descendant(mesh); d.U = mesh.U.copy(); top = d.U[:, 2] > 1.5
        d.U[top, :2] *= 0.9
        out = d.write(self.dir / 'd.glb')
        self.assertTrue(np.array_equal(out.prims[0]['uv'], mesh.prims[0]['uv']))
        self.assertTrue(np.array_equal(out.prims[0]['idx'], mesh.prims[0]['idx']))
        bottom = mesh.prims[0]['pos'][:, 2] < 0.5
        self.assertTrue(np.array_equal(out.prims[0]['nrm'][bottom], mesh.prims[0]['nrm'][bottom]))
        self.assertTrue(np.allclose(np.linalg.norm(out.prims[0]['nrm'], axis=1), 1, atol=1e-5))
        self.assertTrue((self.dir / 'd.face-source.npy').exists())

    def test_mirror_transport(self):
        pos, faces = capped_cylinder(x0=0.5)
        write_test_glb(self.dir / 'l.glb', pos, faces)
        mpos = pos * [-1, 1, 1]
        write_test_glb(self.dir / 'r.glb', mpos, faces[:, [0, 2, 1]])
        left, right = Mesh(self.dir / 'l.glb'), Mesh(self.dir / 'r.glb')
        mapping, err = mirror_corner_map(left, right)
        self.assertLess(err, 1e-6)
        d = Descendant(left); d.U = left.U + np.array([0.01, 0.02, 0])
        r, _ = mirror_descendant(left, d, right)
        self.assertTrue(np.allclose(r.U - right.U, [-0.01, 0.02, 0]))
        d.write(self.dir / 'ld.glb')
        self.assertTrue(np.allclose(transported_positions(left, Mesh(self.dir / 'ld.glb')), d.U, atol=1e-6))

    def test_topology_rebuild_and_preview(self):
        pos, faces = capped_cylinder()
        write_test_glb(self.dir / 'm.glb', pos, faces)
        mesh = Mesh(self.dir / 'm.glb')
        P, N, T = mesh.corners()
        write_preview(self.dir / 'm.glb', P, N, T, self.dir / 'template.glb')
        tp, _, tt = preview_corners(self.dir / 'template.glb')
        self.assertTrue(np.allclose(tp, P, atol=1e-6))
        d = Descendant(mesh)
        topfan = np.flatnonzero(mesh.F.max(1) == mesh.F.max())  # faces using the top centre vertex
        keep = np.setdiff1d(np.arange(len(mesh.F)), topfan)
        newv = len(d.U); d.U = np.vstack([d.U, [0, 0, 2.2]])
        rim = np.unique(mesh.F[topfan]); rim = rim[rim != mesh.F.max()]
        fan = mesh.F[topfan].copy(); fan[fan == mesh.F.max()] = newv
        d.F = np.vstack([mesh.F[keep], fan]); d.face_prim = np.zeros(len(d.F), int)
        d.face_source = np.r_[keep, -np.ones(len(fan), int)]; d.extra_uv[newv] = np.array([0.5, 0.5])
        out = d.write(self.dir / 'cap.glb')
        self.assertEqual(closure(out.F)['boundaryEdges'], 0)
        descendant_preview(self.dir / 'template.glb', self.dir / 'm.glb', self.dir / 'cap.glb', self.dir / 'prev.glb',
                           np.load(self.dir / 'cap.face-source.npy'))
        pp, _, _ = preview_corners(self.dir / 'prev.glb')
        self.assertEqual(len(pp), len(out.F))

    def test_corner_uv_override_only_changes_named_faces(self):
        pos, faces = capped_cylinder()
        write_test_glb(self.dir / 'm.glb', pos, faces)
        mesh = Mesh(self.dir / 'm.glb'); P, N, T = mesh.corners()
        d = Descendant(mesh)
        tri = np.array([[0.9, 0.9], [0.95, 0.9], [0.9, 0.95]])
        d.corner_uv_override[3] = tri
        out = d.write(self.dir / 'uv.glb'); P2, N2, T2 = out.corners()
        self.assertTrue(np.allclose(T2[3], tri, atol=1e-6))
        others = np.setdiff1d(np.arange(len(T)), [3])
        self.assertTrue(np.allclose(T2[others], T[others], atol=1e-7))
        self.assertTrue(np.allclose(P2, P, atol=1e-6))
        self.assertEqual(closure(out.F)['boundaryEdges'], closure(mesh.F)['boundaryEdges'])

    def test_similarity_wrapper_round_trip(self):
        pos, faces = capped_cylinder()
        write_test_glb(self.dir / 'w.glb', pos, faces)
        from place_purposebuilt_pelvis import read_glb
        from round_generated_waist_cap import write_glb as wg
        doc, binary = read_glb(self.dir / 'w.glb')
        c, s_ = np.cos(0.07), np.sin(0.07)
        doc['nodes'].append({'matrix': [1, 0, 0, 0, 0, c, -s_, 0, 0, s_, c, 0, 0, 0.01, 0.02, 1], 'children': [0]})
        doc['scenes'][0]['nodes'] = [1]
        wg(self.dir / 'w2.glb', doc, bytearray(binary))
        mesh = Mesh(self.dir / 'w2.glb')
        self.assertTrue(mesh.wrapped)
        d = Descendant(mesh); top = mesh.U[:, 2] > mesh.U[:, 2].max() - 0.3
        d.U = mesh.U.copy(); d.U[top] += [0, 0, 0.01]
        out = d.write(self.dir / 'w3.glb')
        self.assertTrue(np.allclose(transported_positions(mesh, out), d.U, atol=1e-6))
        doc2, bin2 = read_glb(self.dir / 'w3.glb'); doc1, bin1 = read_glb(self.dir / 'w2.glb')
        from place_purposebuilt_pelvis import accessor
        a1 = accessor(doc1, bin1, doc1['meshes'][0]['primitives'][0]['attributes']['POSITION'])
        a2 = accessor(doc2, bin2, doc2['meshes'][0]['primitives'][0]['attributes']['POSITION'])
        still = ~np.isin(mesh.prims[0]['vid'], np.flatnonzero(top))
        self.assertTrue(np.array_equal(a1[still], a2[still]))

    def test_weighted_smoothing_keeps_fixed_vertices(self):
        pos, faces = capped_cylinder()
        U = pos + np.random.default_rng(1).normal(0, 0.01, pos.shape)
        w = (pos[:, 2] > 1).astype(float)
        X = laplacian_smooth(U, faces, w, 5, normal_only=True)
        self.assertTrue(np.array_equal(X[w == 0], U[w == 0]))


if __name__ == '__main__':
    unittest.main()
