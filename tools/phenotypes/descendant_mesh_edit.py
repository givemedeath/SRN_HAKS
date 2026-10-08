"""Versioned GLB geometry descendants of a fitted part master.

Shared core for measured geometry edits on detached, identity-node part masters:
exact-position welding, displacement application, transported authored normals
(the authored normal is rotated by the change of the geometric normal, so the
edit band meets untouched shading continuously), tangent re-orthogonalization,
optional topology edits on one primitive, exact left->right mirror transport and
preview-GLB (PLT-colorized corner soup) transport. Maps, materials, UV values of
retained vertices and untouched accessors stay byte-identical; new accessors are
appended to the original BIN.

Coordinates: NWN part-local (Z up, +Y anterior). glTF stores p_gltf = p_nwn @ BASIS.
"""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from place_purposebuilt_pelvis import BASIS, read_glb, accessor, embedded_maps, node_matrix
from round_generated_waist_cap import append_accessor, write_glb

MIRROR = np.diag([-1., 1., 1.])


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Mesh:
    """Indexed primitives of one identity-node GLB master in NWN coordinates, plus exact welding."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.doc, binary = read_glb(self.path)
        self.binary = bytes(binary)
        require(not self.doc.get('skins') and not self.doc.get('animations'), 'Static detached master required')
        meshes = [i for i, n in enumerate(self.doc['nodes']) if 'mesh' in n]
        require(len(meshes) == 1, 'Exactly one mesh node required')
        node = self.doc['nodes'][meshes[0]]
        require('children' not in node, 'Mesh node must be a leaf')
        # accumulate an optional similarity wrapper (e.g. a declared postfit similarity on a parent node)
        parents = {c: i for i, n in enumerate(self.doc['nodes']) for c in n.get('children', [])}
        M = np.eye(4); cur = meshes[0]
        while cur is not None:
            M = node_matrix(self.doc['nodes'][cur]) @ M; cur = parents.get(cur)
        lin = M[:3, :3]; scale = float(np.cbrt(np.linalg.det(lin)))
        require(scale > 0 and np.allclose(lin.T @ lin, np.eye(3) * scale ** 2, atol=1e-9), 'Similarity wrapper required')
        self.M = M; self.Minv = np.linalg.inv(M); self.R = lin / scale
        self.wrapped = not np.allclose(M, np.eye(4), atol=0)
        self.mesh_index = node['mesh']
        self.prims = []
        for pindex, prim in enumerate(self.doc['meshes'][self.mesh_index]['primitives']):
            attr = prim['attributes']
            require(prim.get('mode', 4) == 4 and not prim.get('targets') and not prim.get('extensions'), 'Indexed static triangles required')
            require(not set(attr) - {'POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT'}, 'Unsupported attribute: ' + str(sorted(attr)))
            raw_pos = accessor(self.doc, self.binary, attr['POSITION'])
            pos = (np.c_[raw_pos.astype(float), np.ones(len(raw_pos))] @ self.M.T)[:, :3] @ BASIS.T
            nrm = accessor(self.doc, self.binary, attr['NORMAL']).astype(float) @ self.R.T @ BASIS.T
            uv = accessor(self.doc, self.binary, attr['TEXCOORD_0']).astype(float)
            tan = None
            if 'TANGENT' in attr:
                tan = accessor(self.doc, self.binary, attr['TANGENT']).astype(float)
                tan[:, :3] = tan[:, :3] @ self.R.T @ BASIS.T
            idx = accessor(self.doc, self.binary, prim['indices']).reshape(-1, 3).astype(np.int64)
            self.prims.append(dict(index=pindex, material=prim.get('material'), pos=pos, nrm=nrm, uv=uv, tan=tan, idx=idx))
        self._weld()

    def _weld(self):
        allpos = np.concatenate([p['pos'] for p in self.prims])
        self.U, inverse = np.unique(allpos, axis=0, return_inverse=True)
        inverse = inverse.reshape(-1)
        offset = 0
        faces = []; owner = []
        for p in self.prims:
            p['vid'] = inverse[offset:offset + len(p['pos'])]; offset += len(p['pos'])
            faces.append(p['vid'][p['idx']]); owner.append(np.full(len(p['idx']), p['index']))
        self.F = np.concatenate(faces)
        self.face_prim = np.concatenate(owner)
        self.face_local = np.concatenate([np.arange(len(p['idx'])) for p in self.prims])

    def corners(self):
        """Triangle-corner arrays in primitive order (identical to raw_corners ordering)."""
        P = np.concatenate([p['pos'][p['idx']] for p in self.prims])
        N = np.concatenate([p['nrm'][p['idx']] for p in self.prims])
        T = np.concatenate([p['uv'][p['idx']] for p in self.prims])
        return P, N, T


def edges(F):
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    e = e[e[:, 0] != e[:, 1]]
    return np.unique(e, axis=0, return_counts=True)


def closure(F):
    ue, cnt = edges(F)
    V = len(np.unique(F))
    return dict(boundaryEdges=int((cnt == 1).sum()), nonManifoldEdges=int((cnt > 2).sum()),
                eulerCharacteristic=int(V - len(ue) + len(F)), triangles=int(len(F)))


def neighbours(F, count):
    """CSR adjacency of welded vertices."""
    ue, _ = edges(F)
    a = np.concatenate([ue[:, 0], ue[:, 1]]); b = np.concatenate([ue[:, 1], ue[:, 0]])
    order = np.argsort(a, kind='stable'); a = a[order]; b = b[order]
    start = np.searchsorted(a, np.arange(count + 1))
    return start, b


def face_normals(U, F):
    n = np.cross(U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]])
    return n  # area-weighted (2x area)


def vertex_normals(U, F):
    acc = np.zeros_like(U)
    fn = face_normals(U, F)
    for k in range(3):
        np.add.at(acc, F[:, k], fn)
    length = np.linalg.norm(acc, axis=1)
    out = np.zeros_like(acc)
    good = length > 1e-20
    out[good] = acc[good] / length[good, None]
    return out


def smoothed_vertex_normals(U, F, iterations=3):
    """Area-weighted vertex normals averaged over the 1-ring (suppresses irregular-triangulation noise)."""
    n = vertex_normals(U, F)
    if iterations <= 0:
        return n
    start, nb = neighbours(F, len(U)); deg = np.diff(start); rows = np.repeat(np.arange(len(U)), deg)
    for _ in range(iterations):
        acc = n.copy(); np.add.at(acc, rows, n[nb])
        n = acc / np.maximum(np.linalg.norm(acc, axis=1), 1e-20)[:, None]
    return n


def rotate_between(a, b, v):
    """Rotate rows v by the minimal rotation taking unit a onto unit b (Rodrigues, per row)."""
    axis = np.cross(a, b)
    s = np.linalg.norm(axis, axis=1); c = np.sum(a * b, axis=1)
    out = v.copy()
    m = s > 1e-12
    k = axis[m] / s[m, None]
    vm = v[m]
    out[m] = vm * c[m, None] + np.cross(k, vm) * s[m, None] + k * np.sum(k * vm, axis=1)[:, None] * (1 - c[m])[:, None]
    flip = (~m) & (c < 0)
    out[flip] = -v[flip]
    return out


def laplacian_smooth(U, F, weights, iterations, lam=0.5, mu=-0.53, normal_only=False):
    """Weighted Taubin smoothing; weights in [0,1] per welded vertex (0 = fixed).
    normal_only projects each update on the current vertex normal (no tangential drift/collapse)."""
    start, nb = neighbours(F, len(U))
    deg = np.diff(start)
    w = np.asarray(weights, float)
    X = U.copy()
    idx_rows = np.repeat(np.arange(len(U)), deg)
    for _ in range(iterations):
        for factor in (lam, mu):
            mean = np.zeros_like(X)
            np.add.at(mean, idx_rows, X[nb])
            safe = np.maximum(deg, 1)[:, None]
            L = mean / safe - X
            L[deg == 0] = 0
            if normal_only:
                n = vertex_normals(X, F)
                L = n * np.sum(L * n, axis=1)[:, None]
            X = X + factor * w[:, None] * L
    return X


class Descendant:
    """Accumulates welded-position edits and optional topology edits for one master."""

    def __init__(self, mesh):
        self.mesh = mesh
        self.U = mesh.U.copy()
        self.F = mesh.F.copy()
        self.face_prim = mesh.face_prim.copy()
        self.face_source = np.arange(len(mesh.F))  # original global triangle index, -1 for new faces
        self.extra_uv = {}  # welded id of new vertices -> uv per primitive
        self.normal_smoothing = 3
        self.corner_uv_override = {}  # global face index -> (3, 2) UVs (forces a rebuild of that primitive)  # 1-ring averaging passes for the geometric normals whose change rotates authored normals
        self.authored = None

    @property
    def topology_changed(self):
        return len(self.F) != len(self.mesh.F) or not np.array_equal(self.F, self.mesh.F)

    def displaced(self):
        n0 = len(self.mesh.U)
        moved = np.zeros(len(self.U), bool)
        moved[:n0] = np.any(self.U[:n0] != self.mesh.U, axis=1)
        moved[n0:] = True
        return moved

    def build(self):
        """Return per-primitive new arrays (pos, nrm, uv, tan, idx) and whether each primitive changed topology."""
        mesh = self.mesh
        geo_old = smoothed_vertex_normals(mesh.U, mesh.F, self.normal_smoothing)
        geo_new = smoothed_vertex_normals(self.U, self.F, self.normal_smoothing)
        moved = self.displaced()
        # vertices whose (smoothed) geometric normal changed, plus every vertex of new faces
        touched = np.zeros(len(self.U), bool)
        n0 = len(mesh.U)
        touched[:n0] = np.linalg.norm(geo_new[:n0] - geo_old, axis=1) > 1e-9
        touched[n0:] = True
        new_faces = self.face_source < 0
        if new_faces.any():
            touched[np.unique(self.F[new_faces])] = True
        out = []
        for p in mesh.prims:
            pi = p['index']
            sel = self.face_prim == pi
            faces = self.F[sel]
            src = self.face_source[sel]
            override_rows = np.flatnonzero(sel)
            has_override = any(int(f) in self.corner_uv_override for f in override_rows) if self.corner_uv_override else False
            unchanged_topology = (len(faces) == len(p['idx'])) and np.array_equal(src, np.flatnonzero(mesh.face_prim == pi)) and not has_override
            if unchanged_topology:
                vid = p['vid']
                pos = self.U[vid]
                nrm = p['nrm'].copy(); t = touched[vid]
                nrm[t] = rotate_between(geo_old[vid[t]], geo_new[vid[t]], p['nrm'][t])
                nrm[t] *= (np.linalg.norm(p['nrm'][t], axis=1) / np.maximum(np.linalg.norm(nrm[t], axis=1), 1e-20))[:, None]
                tan = None
                if p['tan'] is not None:
                    tan = p['tan'].copy()
                    if t.any():
                        tt = rotate_between(geo_old[vid[t]], geo_new[vid[t]], p['tan'][t, :3])
                        unit = nrm[t] / np.linalg.norm(nrm[t], axis=1)[:, None]
                        tt -= unit * np.sum(unit * tt, axis=1)[:, None]
                        L = np.linalg.norm(p['tan'][t, :3], axis=1)
                        tt *= (L / np.maximum(np.linalg.norm(tt, axis=1), 1e-20))[:, None]
                        tan[t, :3] = tt
                out.append(dict(index=pi, pos=pos, nrm=nrm, uv=p['uv'], tan=tan, idx=p['idx'], topology=False))
                continue
            if len(faces) == 0:
                out.append(dict(index=pi, removed=True, topology=True))
                continue
            # topology rebuild: one output vertex per (welded id, source uv) pair actually used
            corner_vid = faces.reshape(-1)
            corner_uv = np.zeros((len(corner_vid), 2))
            corner_nrm = np.zeros((len(corner_vid), 3)); corner_tan = np.zeros((len(corner_vid), 4))
            kept = np.repeat(src >= 0, 3)
            # retained faces: take original corner attributes
            src_kept = src[src >= 0]
            local = mesh.face_local[src_kept]
            ocorner = p['idx'][local].reshape(-1)
            corner_uv[kept] = p['uv'][ocorner]
            if has_override:
                for row, f in enumerate(override_rows):
                    if int(f) in self.corner_uv_override:
                        corner_uv[3 * row:3 * row + 3] = self.corner_uv_override[int(f)]
            n_auth = p['nrm'][ocorner]
            cv = corner_vid[kept]
            tk = touched[cv]
            nn = n_auth.copy()
            nn[tk] = rotate_between(geo_old[cv[tk]], geo_new[cv[tk]], n_auth[tk])
            corner_nrm[kept] = nn
            if p['tan'] is not None:
                ta = p['tan'][ocorner].copy()
                if tk.any():
                    tt = rotate_between(geo_old[cv[tk]], geo_new[cv[tk]], ta[tk, :3])
                    unit = nn[tk] / np.linalg.norm(nn[tk], axis=1)[:, None]
                    tt -= unit * np.sum(unit * tt, axis=1)[:, None]
                    tt /= np.maximum(np.linalg.norm(tt, axis=1), 1e-20)[:, None]
                    ta[tk, :3] = tt
                corner_tan[kept] = ta
            # new faces: computed normals, uv from extra_uv
            newc = ~kept
            nv = corner_vid[newc]
            corner_nrm[newc] = geo_new[nv]
            kept_normal = {}
            for v_, n_ in zip(cv, nn):
                kept_normal.setdefault(int(v_), n_)
            shared = np.asarray([int(v_) in kept_normal for v_ in nv], bool)
            if shared.any():
                rows_ = np.flatnonzero(newc)[shared]
                corner_nrm[rows_] = np.asarray([kept_normal[int(v_)] for v_ in nv[shared]])
            kept_uv = {}
            for v_, t_ in zip(cv, corner_uv[kept]):
                kept_uv.setdefault(int(v_), t_)
            def uv_for(v_):
                if int(v_) in kept_uv:
                    return kept_uv[int(v_)]
                require(int(v_) in self.extra_uv, 'New-face vertex lacks an explicit UV')
                return self.extra_uv[int(v_)]
            if len(nv):
                corner_uv[newc] = np.asarray([uv_for(v) for v in nv])
            if p['tan'] is not None:
                # tangent from a stable reference direction orthogonalized to the normal; handedness +1
                ref = np.tile([1., 0, 0], (int(newc.sum()), 1))
                n_ = corner_nrm[newc]
                tt = ref - n_ * np.sum(n_ * ref, axis=1)[:, None]
                bad = np.linalg.norm(tt, axis=1) < 1e-6
                tt[bad] = np.array([0, 1., 0]) - n_[bad] * n_[bad, 1:2]
                tt /= np.linalg.norm(tt, axis=1)[:, None]
                corner_tan[newc] = np.c_[tt, np.ones(len(tt))]
            key = np.c_[corner_vid.astype(float), corner_uv, corner_nrm]
            uniq, inverse = np.unique(key, axis=0, return_inverse=True)
            inverse = inverse.reshape(-1)
            first = np.zeros(len(uniq), np.int64); first[inverse[::-1]] = np.arange(len(inverse))[::-1]
            pos = self.U[corner_vid[first]]
            out.append(dict(index=pi, pos=pos, nrm=corner_nrm[first], uv=corner_uv[first],
                            tan=corner_tan[first] if p['tan'] is not None else None,
                            idx=inverse.reshape(-1, 3), topology=True))
        return out

    def write(self, path):
        mesh = self.mesh
        doc = copy.deepcopy(mesh.doc); binary = bytearray(mesh.binary)
        built = self.build()
        prims = doc['meshes'][mesh.mesh_index]['primitives']
        for row in built:
            if row.get('removed'):
                continue
            attr = prims[row['index']]['attributes']
            moved = not np.array_equal(row['pos'], mesh.prims[row['index']]['pos']) or row['topology']
            if not moved and np.array_equal(row['nrm'], mesh.prims[row['index']]['nrm']):
                continue
            src = mesh.prims[row['index']]
            def to_local(points):
                return (np.c_[points @ BASIS, np.ones(len(points))] @ mesh.Minv.T)[:, :3]
            def keep_rows(new_local, old_attr, changed):
                # untouched rows keep their exact original accessor bytes
                if row['topology']:
                    return new_local.astype('<f4')
                base = accessor(mesh.doc, mesh.binary, old_attr).astype('<f4')
                base[changed] = new_local[changed].astype('<f4')
                return base
            changed_p = np.any(row['pos'] != src['pos'], axis=1) if not row['topology'] else None
            changed_n = np.any(row['nrm'] != src['nrm'], axis=1) if not row['topology'] else None
            oattr = mesh.doc['meshes'][mesh.mesh_index]['primitives'][row['index']]['attributes']
            attr['POSITION'] = append_accessor(doc, binary, keep_rows(to_local(row['pos']), oattr['POSITION'], changed_p), 'POSITION')
            attr['NORMAL'] = append_accessor(doc, binary, keep_rows(row['nrm'] @ BASIS @ mesh.R, oattr['NORMAL'], changed_n), 'NORMAL')
            if row['tan'] is not None:
                t = row['tan'].copy(); t[:, :3] = t[:, :3] @ BASIS @ mesh.R
                if not row['topology']:
                    base = accessor(mesh.doc, mesh.binary, oattr['TANGENT']).astype('<f4')
                    ch = np.any(row['tan'] != src['tan'], axis=1); base[ch] = t[ch].astype('<f4'); t = base
                attr['TANGENT'] = append_accessor(doc, binary, t.astype('<f4'), 'TANGENT')
            if row['topology']:
                attr['TEXCOORD_0'] = append_accessor(doc, binary, row['uv'].astype('<f4'), 'TEXCOORD_0')
                prims[row['index']]['indices'] = append_accessor(doc, binary, row['idx'].reshape(-1, 1).astype('<u4'))
        removed = [row['index'] for row in built if row.get('removed')]
        for index in sorted(removed, reverse=True):
            del prims[index]
        built = [row for row in built if not row.get('removed')]
        path = Path(path)
        write_glb(path, doc, binary)
        # source triangle (parent global index, -1 new) for every output triangle in output primitive order
        order = np.concatenate([np.flatnonzero(self.face_prim == row['index']) for row in built])
        np.save(path.with_suffix('.face-source.npy'), self.face_source[order])
        check = Mesh(path)
        require(embedded_maps(check.doc, check.binary) == embedded_maps(mesh.doc, mesh.binary), 'Embedded maps changed')
        require(check.doc.get('materials') == mesh.doc.get('materials'), 'Materials changed')
        require(check.binary[:len(mesh.binary)] == mesh.binary, 'Original BIN bytes changed')
        for row, cp in zip(built, check.prims):
            require(np.abs(cp['pos'] - row['pos']).max() < 1e-6, 'Position transport mismatch')
            if not row['topology']:
                require(np.array_equal(cp['uv'], mesh.prims[row['index']]['uv']), 'Retained UVs changed')
                require(np.array_equal(cp['idx'], mesh.prims[row['index']]['idx']), 'Retained indices changed')
        return check


def summary(desc, label):
    n0 = len(desc.mesh.U)
    disp = np.linalg.norm(desc.U[:n0] - desc.mesh.U, axis=1)
    moved = np.r_[disp > 1e-7, np.ones(len(desc.U) - n0, bool)]
    return dict(label=label, movedVerticesOver0p1um=int(moved[:n0].sum()), newVertices=int(len(desc.U) - n0),
                maxDisplacementMeters=float(disp.max()), meanDisplacementMovedMeters=float(disp[moved[:n0]].mean()) if moved[:n0].any() else 0.0,
                before=closure(desc.mesh.F), after=closure(desc.F))


def transported_positions(master, final):
    """Welded master-vertex positions taken from a position-only descendant (same primitives/indices/vertex order)."""
    require(len(master.prims) == len(final.prims), 'Primitive count changed')
    U = master.U.copy(); seen = np.zeros(len(U), bool)
    for a, b in zip(master.prims, final.prims):
        require(np.array_equal(a['idx'], b['idx']) and len(a['pos']) == len(b['pos']), 'Position-only descendant required')
        U[a['vid']] = b['pos']; seen[a['vid']] = True
        require(np.abs(U[a['vid']] - b['pos']).max() == 0, 'Welded copies moved differently')
    require(seen.all(), 'Unmapped welded vertices')
    return U


def mirror_corner_map(left, right, tolerance=2e-5):
    """Welded right vertex -> welded left vertex via identical triangle order with corners 1/2 swapped and x negated."""
    PL, _, _ = left.corners(); PR, _, _ = right.corners()
    require(PL.shape == PR.shape, 'Left/right triangle counts differ')
    m = PL.copy(); m[..., 0] *= -1
    err = np.abs(m[:, [0, 2, 1]] - PR).max()
    require(err < tolerance, 'Right master is not the corner-swapped mirror of left (%.3g m)' % err)
    FL = left.F; FR = right.F
    mapping = np.full(len(right.U), -1, np.int64)
    mapping[FR[:, [0, 2, 1]].reshape(-1)] = FL.reshape(-1)
    require((mapping >= 0).all(), 'Unmapped right vertices')
    return mapping, float(err)


def mirror_descendant(left_mesh, left_desc, right_mesh):
    """Apply the mirrored left displacement to the right master; topology must be unchanged."""
    require(not left_desc.topology_changed, 'Mirror transport supports position-only descendants')
    mapping, err = mirror_corner_map(left_mesh, right_mesh)
    delta = (left_desc.U - left_mesh.U)[mapping] @ MIRROR
    right = Descendant(right_mesh)
    right.U = right_mesh.U + delta
    return right, err


def write_preview(template, corners_P, corners_N, corners_UV, path, name=None):
    """Write a PLT-colorized preview GLB (single primitive corner soup) carrying the template's material/images."""
    doc, binary = read_glb(template)
    doc = copy.deepcopy(doc); binary = bytearray(binary)
    meshes = doc['meshes']
    require(len(meshes) == 1 and len(meshes[0]['primitives']) == 1, 'Single-primitive preview template required')
    prim = meshes[0]['primitives'][0]
    P = np.asarray(corners_P, float).reshape(-1, 3); N = np.asarray(corners_N, float).reshape(-1, 3)
    T = np.asarray(corners_UV, float).reshape(-1, 2)
    N = N / np.maximum(np.linalg.norm(N, axis=1), 1e-20)[:, None]
    prim['attributes'] = {'POSITION': append_accessor(doc, binary, (P @ BASIS).astype('<f4'), 'POSITION'),
                          'NORMAL': append_accessor(doc, binary, (N @ BASIS).astype('<f4'), 'NORMAL'),
                          'TEXCOORD_0': append_accessor(doc, binary, T.astype('<f4'), 'TEXCOORD_0')}
    prim['indices'] = append_accessor(doc, binary, np.arange(len(P), dtype='<u4').reshape(-1, 1))
    if name:
        doc['nodes'][0]['name'] = name
    write_glb(Path(path), doc, binary)


def preview_corners(template):
    """Corner soup (P, N, UV) of every primitive of a preview GLB, in primitive order."""
    doc, binary = read_glb(template)
    out = [[], [], []]
    for prim in doc['meshes'][0]['primitives']:
        P = accessor(doc, binary, prim['attributes']['POSITION']).astype(float) @ BASIS.T
        N = accessor(doc, binary, prim['attributes']['NORMAL']).astype(float) @ BASIS.T
        T = accessor(doc, binary, prim['attributes']['TEXCOORD_0']).astype(float)
        idx = accessor(doc, binary, prim['indices']).reshape(-1).astype(np.int64)
        out[0].append(P[idx].reshape(-1, 3, 3)); out[1].append(N[idx].reshape(-1, 3, 3)); out[2].append(T[idx].reshape(-1, 3, 2))
    return tuple(np.concatenate(x) for x in out)


def descendant_preview(template, master_path, descendant_path, path, face_source=None):
    """Preview for a descendant (possibly a chain): triangles with a source keep the template's native UVs
    (the template corners must equal the master corners); new triangles take the native UV of the nearest
    retained corner. Positions/normals come from the written descendant."""
    tP, tN, tT = preview_corners(template)
    master = Mesh(master_path)
    mP, _, _ = master.corners()
    require(tP.shape == mP.shape and np.abs(tP - mP).max() < 1e-6, 'Preview template corners differ from master corners')
    built = Mesh(descendant_path)
    P, N, _ = built.corners()
    source = np.arange(len(P)) if face_source is None else np.asarray(face_source)
    require(len(source) == len(P), 'Face source length mismatch')
    UV = np.zeros((len(source), 3, 2))
    keep = source >= 0
    UV[keep] = tT[source[keep]]
    if (~keep).any():
        flatP = P[keep].reshape(-1, 3); flatT = UV[keep].reshape(-1, 2)
        q = P[~keep].reshape(-1, 3)
        lo = q.min(0) - 0.03; hi = q.max(0) + 0.03
        pool = np.flatnonzero(np.all((flatP >= lo) & (flatP <= hi), axis=1))
        require(len(pool) > 0, 'No retained corners near new triangles')
        nearest = np.empty(len(q), np.int64)
        for s0 in range(0, len(q), 256):
            d = ((q[s0:s0 + 256, None, :] - flatP[pool][None, :, :]) ** 2).sum(-1)
            nearest[s0:s0 + 256] = pool[d.argmin(1)]
        UV[~keep] = flatT[nearest].reshape(-1, 3, 2)
    write_preview(template, P, N, UV, path)


def transported_preview(template, master_path, descendant_path, path, tolerance=1e-6):
    """Position-only descendants of a multi-primitive preview: every template vertex is matched to the master's
    welded vertex by position, moved by the descendant displacement; normals rotated by the geometric change."""
    master = Mesh(master_path); final = Mesh(descendant_path)
    U1 = transported_positions(master, final)
    key = {tuple(k): i for i, k in enumerate(np.round(master.U / tolerance).astype(np.int64))}
    g0 = smoothed_vertex_normals(master.U, master.F); g1 = smoothed_vertex_normals(U1, master.F)
    doc, binary = read_glb(template); doc = copy.deepcopy(doc); binary = bytearray(binary)
    for prim in doc['meshes'][0]['primitives']:
        P = accessor(doc, binary, prim['attributes']['POSITION']).astype(float) @ BASIS.T
        N = accessor(doc, binary, prim['attributes']['NORMAL']).astype(float) @ BASIS.T
        ids = np.array([key.get(tuple(k), -1) for k in np.round(P / tolerance).astype(np.int64)])
        if (ids < 0).any():  # tolerate float noise: nearest within 1e-5 m
            for i in np.flatnonzero(ids < 0):
                d = np.linalg.norm(master.U - P[i], axis=1); j = int(d.argmin())
                require(d[j] < 1e-5, 'Preview vertex not found on the master')
                ids[i] = j
        newP = U1[ids]; moved = np.any(newP != master.U[ids], axis=1)
        newN = N.copy(); newN[moved] = rotate_between(g0[ids[moved]], g1[ids[moved]], N[moved])
        prim['attributes']['POSITION'] = append_accessor(doc, binary, (newP @ BASIS).astype('<f4'), 'POSITION')
        prim['attributes']['NORMAL'] = append_accessor(doc, binary, (newN @ BASIS).astype('<f4'), 'NORMAL')
    write_glb(Path(path), doc, binary)


def write_receipt(path, record):
    Path(path).write_text(json.dumps(record, indent=2, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)) + '\n')


def main():
    import argparse
    import shutil
    ap = argparse.ArgumentParser(description='Mirror a left position-only descendant chain onto the right master, or write a preview GLB.')
    sub = ap.add_subparsers(dest='command', required=True)
    m = sub.add_parser('mirror')
    for key in ('left-master', 'left-descendant', 'right-master', 'output'):
        m.add_argument('--' + key, type=Path, required=True)
    m.add_argument('--name', required=True)
    p = sub.add_parser('preview')
    for key in ('template', 'master', 'descendant', 'output'):
        p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--face-source', type=Path)
    p.add_argument('--by-position', action='store_true', help='multi-primitive template; position-only descendant')
    a = ap.parse_args()
    if a.command == 'mirror':
        require(not a.output.exists(), 'Fresh mirror directory required')
        left = Mesh(a.left_master); right = Mesh(a.right_master); final = Mesh(a.left_descendant)
        chain = Descendant(left); chain.U = transported_positions(left, final)
        desc, err = mirror_descendant(left, chain, right)
        a.output.mkdir(parents=True)
        out = a.output / (a.name + '-local.glb')
        desc.write(out)
        rec = dict(schemaVersion=1, kind='mirrored-descendant', leftMaster={'path': str(a.left_master), 'sha256': sha(a.left_master)},
                   leftDescendant={'path': str(a.left_descendant), 'sha256': sha(a.left_descendant)},
                   rightMaster={'path': str(a.right_master), 'sha256': sha(a.right_master)}, descendant={'path': str(out), 'sha256': sha(out)},
                   masterMirrorResidualMeters=err, summary=summary(desc, a.name), helperSha256=sha(__file__),
                   policy='Right = right master + x-mirrored left displacement per corner-matched vertex; normals transported; UV/index/maps exact.')
        write_receipt(a.output / 'descendant.json', rec)
        shutil.copy2(__file__, a.output / 'executed-helper.py')
        print(json.dumps({'output': str(out), 'residual': err, 'moved': rec['summary']['movedVerticesOver0p1um']}))
    else:
        require(not a.output.exists(), 'Fresh preview path required')
        if a.by_position:
            transported_preview(a.template, a.master, a.descendant, a.output)
        else:
            fs = np.load(a.face_source) if a.face_source else None
            descendant_preview(a.template, a.master, a.descendant, a.output, fs)
        print(json.dumps({'preview': str(a.output), 'sha256': sha(a.output)}))


if __name__ == '__main__':
    main()
