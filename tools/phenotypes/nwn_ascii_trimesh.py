"""NWN ASCII trimesh models: parse, map to GLB corners, write edited geometry, and export previews.

Only `node trimesh` / `node dummy` models of detached parts and heads are supported (no skin/anim nodes).
Text outside the edited sections is preserved byte for byte (line endings included). ASCII texture V is
bottom-up; glTF/GLB corner UVs are top-down, so v_gltf = 1 - v_ascii.
"""
import re
import numpy as np

SECTIONS = ('verts', 'normals', 'tverts', 'faces')


def fmt(x):
    """Float text like the compiler-facing v1 sources: shortest round-trip of the float32 value, 17 digits."""
    v = float(np.float32(x))
    if v == 0:
        return '0'
    return '%.17g' % v


class Node:
    def __init__(self, kind, name, start):
        self.kind, self.name, self.start, self.end = kind, name, start, None
        self.fields = {}
        self.sections = {}   # key -> (header line index, count)


class AsciiModel:
    def __init__(self, text):
        self.newline = '\r\n' if '\r\n' in text else '\n'
        self.trailing = text.endswith(self.newline)
        body = text[:-len(self.newline)] if self.trailing else text
        self.lines = body.split(self.newline)
        self.parse()

    @classmethod
    def read(cls, path):
        return cls(open(path, 'rb').read().decode('cp1252'))

    def text(self):
        return self.newline.join(self.lines) + (self.newline if self.trailing else '')

    def write(self, path):
        open(path, 'wb').write(self.text().encode('cp1252'))

    def parse(self):
        self.nodes = []
        node = None; i = 0; L = self.lines
        while i < len(L):
            s = L[i].strip(); parts = s.split()
            if parts[:1] == ['node'] and len(parts) >= 3:
                node = Node(parts[1], parts[2], i); self.nodes.append(node)
            elif parts[:1] == ['endnode'] and node is not None:
                node.end = i; node = None
            elif node is not None and parts:
                key = parts[0].lower()
                if key in SECTIONS and len(parts) == 2 and parts[1].isdigit():
                    n = int(parts[1]); node.sections[key] = (i, n); i += n + 1; continue
                node.fields[key] = parts[1:]
            i += 1
        for n in self.nodes:
            if n.end is None:
                raise ValueError('Unterminated node ' + n.name)

    def node(self, name):
        found = [n for n in self.nodes if n.name.lower() == name.lower()]
        if len(found) != 1:
            raise KeyError('Node not found or ambiguous: ' + name)
        return found[0]

    def trimeshes(self):
        return [n for n in self.nodes if n.kind.lower() == 'trimesh']

    def section(self, node, key, dtype=float):
        h, n = node.sections[key]
        rows = [self.lines[h + 1 + k].split() for k in range(n)]
        return np.array(rows, dtype=dtype).reshape(n, -1) if n else np.zeros((0, 8 if key == 'faces' else 3), dtype)

    def arrays(self, node):
        V = self.section(node, 'verts'); N = self.section(node, 'normals') if 'normals' in node.sections else None
        TV = self.section(node, 'tverts'); F = self.section(node, 'faces', np.int64)
        return V, N, TV, F

    def corners(self, node):
        """Corner positions (m,3,3), ascii-V UVs (m,3,2) and normals (m,3,3) in face order."""
        V, N, TV, F = self.arrays(node)
        P = V[F[:, 0:3]]; T = TV[F[:, 4:7], :2]
        return P, T, (N[F[:, 0:3]] if N is not None else None)

    def replace_section(self, node, key, rows):
        """Replace a section's rows (strings); later line indices of every node are re-parsed."""
        h, n = node.sections[key]
        indent = re.match(r'\s*', self.lines[h]).group(0)
        row_indent = re.match(r'\s*', self.lines[h + 1]).group(0) if n else indent + '  '
        self.lines[h:h + 1 + n] = [indent + key + ' ' + str(len(rows))] + [row_indent + r for r in rows]
        self.parse()

    def set_vectors(self, node, key, values, keep_equal=1e-9):
        """Rewrite verts/normals values; rows whose value is unchanged keep their original text exactly."""
        h, n = node.sections[key]
        old = self.section(node, key)
        if len(values) != n:
            raise ValueError('Row count differs for ' + key)
        indent = re.match(r'\s*', self.lines[h + 1]).group(0) if n else '    '
        changed = 0
        for k in range(n):
            if np.abs(old[k, :3] - values[k]).max() > keep_equal:
                self.lines[h + 1 + k] = indent + ' '.join(fmt(x) for x in values[k]); changed += 1
        return changed


def corner_keys(P, T, pos_q=1e-5, uv_q=1e-5):
    """Rotation-invariant per-face key (sorted corner tuples) plus per-corner keys."""
    cp = np.round(P / pos_q).astype(np.int64); ct = np.round(T / uv_q).astype(np.int64)
    ck = np.concatenate([cp, ct], axis=2)                    # (m,3,5)
    return ck


def match_corners(P_a, T_a, P_b, T_b, pos_q=1e-5, uv_q=1e-5):
    """For each face of A find the face of B with the same corners (any rotation) and the corner permutation.
    UVs must use the same convention. Returns (face_index_in_B, perm) with A[f, k] == B[face[f], perm[f, k]].
    Faces whose rounded keys straddle a quantisation boundary are resolved by nearest centroid + corner."""
    ka = corner_keys(P_a, T_a, pos_q, uv_q); kb = corner_keys(P_b, T_b, pos_q, uv_q)
    index = {}
    for f in range(len(kb)):
        key = tuple(sorted(map(tuple, kb[f])))
        index.setdefault(key, []).append(f)
    face = np.full(len(ka), -1, np.int64); perm = np.zeros((len(ka), 3), np.int64)
    used = np.zeros(len(kb), bool)
    pending = []
    for f in range(len(ka)):
        cands = [g for g in index.get(tuple(sorted(map(tuple, ka[f]))), []) if not used[g]]
        if not cands:
            pending.append(f); continue
        g = cands[0]; used[g] = True; face[f] = g
        for k in range(3):
            perm[f, k] = [tuple(x) for x in kb[g]].index(tuple(ka[f, k]))
    if pending:
        ca = P_a[pending].mean(1); free = np.flatnonzero(~used); cb = P_b[free].mean(1)
        for i, f in enumerate(pending):
            d = np.linalg.norm(cb - ca[i], axis=1) + np.linalg.norm(T_b[free].mean(1) - T_a[f].mean(0), axis=1)
            j = int(np.argmin(d)); g = int(free[j])
            if used[g]:
                raise ValueError('Ambiguous corner match')
            used[g] = True; face[f] = g
            for k in range(3):
                e = np.linalg.norm(P_b[g] - P_a[f, k], axis=1) + np.linalg.norm(T_b[g] - T_a[f, k], axis=1)
                perm[f, k] = int(np.argmin(e))
    if len(set(face.tolist())) != len(face):
        raise ValueError('Corner match is not one-to-one')
    # corner permutation: the one of the six orders with the smallest corner error (cyclic orders listed first,
    # so near-coincident corners resolve to the winding-preserving order)
    orders = np.array([[0, 1, 2], [1, 2, 0], [2, 0, 1], [0, 2, 1], [2, 1, 0], [1, 0, 2]])
    err = np.stack([np.abs(P_b[face[:, None], o[None]] - P_a).reshape(len(face), -1).max(1)
                    + np.abs(T_b[face[:, None], o[None]] - T_a).reshape(len(face), -1).max(1) for o in orders], 1)
    perm = orders[np.argmin(err, axis=1)]
    err_p = np.abs(P_b[face[:, None], perm] - P_a).max() if len(face) else 0.0
    err_t = np.abs(T_b[face[:, None], perm] - T_a).max() if len(face) else 0.0
    return face, perm, float(err_p), float(err_t)


def vertex_average(index, values, count):
    """Mean of corner values per vertex index (corners flattened)."""
    acc = np.zeros((count, values.shape[-1])); n = np.zeros(count)
    np.add.at(acc, index.reshape(-1), values.reshape(-1, values.shape[-1])); np.add.at(n, index.reshape(-1), 1)
    return acc / np.maximum(n, 1)[:, None], n


def vertex_spread(index, values, mean):
    d = np.linalg.norm(values.reshape(-1, values.shape[-1]) - mean[index.reshape(-1)], axis=1)
    return float(d.max()) if len(d) else 0.0


def rebuild_rows(P, N, T, groups, materials):
    """Node rows from corner arrays: welded verts (exact float32 positions), per-vertex mean normals, unique tverts."""
    p32 = np.asarray(P, np.float32).reshape(-1, 3)
    vkey, vinv = np.unique(p32.view([('', np.float32)] * 3).reshape(-1), return_inverse=True)
    order = np.zeros(len(vkey), np.int64); seen = np.zeros(len(vkey), bool); nxt = 0
    for c in vinv:                       # first-appearance order keeps the file stable and readable
        if not seen[c]:
            seen[c] = True; order[c] = nxt; nxt += 1
    vi = order[vinv].reshape(-1, 3)
    V = np.zeros((len(vkey), 3)); V[vi.reshape(-1)] = p32.astype(float)
    Nn, _ = vertex_average(vi, np.asarray(N, float), len(V)); Nn /= np.maximum(np.linalg.norm(Nn, axis=1), 1e-12)[:, None]
    t32 = np.asarray(T, np.float32).reshape(-1, 2)
    tkey, tinv = np.unique(t32.view([('', np.float32)] * 2).reshape(-1), return_inverse=True)
    torder = np.zeros(len(tkey), np.int64); seen = np.zeros(len(tkey), bool); nxt = 0
    for c in tinv:
        if not seen[c]:
            seen[c] = True; torder[c] = nxt; nxt += 1
    ti = torder[tinv].reshape(-1, 3)
    TV = np.zeros((len(tkey), 2)); TV[ti.reshape(-1)] = t32.astype(float)
    verts = [' '.join(fmt(x) for x in v) for v in V]
    normals = [' '.join(fmt(x) for x in n) for n in Nn]
    tverts = [fmt(t[0]) + ' ' + fmt(t[1]) + ' 0' for t in TV]
    faces = ['%d %d %d %d %d %d %d %d' % (a[0], a[1], a[2], g, b[0], b[1], b[2], m) for a, b, g, m in zip(vi, ti, groups, materials)]
    return dict(verts=verts, normals=normals, tverts=tverts, faces=faces), dict(V=V, N=Nn, TV=TV, vi=vi, ti=ti)


def closure(F):
    """Boundary / non-manifold edge counts of an indexed triangle list."""
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    return dict(boundaryEdges=int((cnt == 1).sum()), nonManifoldEdges=int((cnt > 2).sum()), triangles=int(len(F)))


def weld(P, tol=1e-6):
    """Indexed faces from corner positions by quantised welding (for closure checks)."""
    q = np.round(np.asarray(P).reshape(-1, 3) / tol).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    return inv.reshape(-1, 3)
