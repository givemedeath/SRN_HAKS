"""Close a double-walled part's open aperture (e.g. a torso neck collar) with a smooth domed cap.

1. Classify the closed vessel surface into outer skin and hidden inner wall: flood fill from the
   outermost face across faces whose normal faces outward (normal . radial > threshold); the
   largest remaining component is the inner wall, stray concave outer pockets return to the skin.
2. Remove the inner wall and the rolled lip (outer faces above lipCut within lipRadius of the aperture
   axis). One clean aperture loop remains.
3. Build a cap: per loop vertex a cubic Bezier in its radial/vertical plane leaving tangent to the
   local wall and arriving horizontal at the apex; rings are resampled by arc length (counts taper
   toward the apex) and zipped. Cap vertices take the UV of the nearest loop vertex by angle
   (provisional; material bake is a later stage).
4. Weighted Taubin blend over the cap and a cosine band of the skin around the loop.
5. Small residual holes (pinholes) are fan-filled; remaining non-manifold edges are reported.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from descendant_mesh_edit import (Mesh, Descendant, summary, require, sha, write_receipt, face_normals, closure, edges,
                                  laplacian_smooth, vertex_normals)


def face_adjacency(F):
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); fid = np.tile(np.arange(len(F)), 3)
    e.sort(1)
    o = np.lexsort((e[:, 1], e[:, 0])); e = e[o]; fid = fid[o]
    i = np.flatnonzero(np.all(e[1:] == e[:-1], 1))
    return np.c_[fid[i], fid[i + 1]]


def components(nf, pairs, mask):
    p = np.arange(nf)
    def find(x):
        while p[x] != x:
            p[x] = p[p[x]]; x = p[x]
        return x
    for a, b in pairs[mask[pairs[:, 0]] & mask[pairs[:, 1]]]:
        ra, rb = find(a), find(b)
        if ra != rb:
            p[ra] = rb
    r = np.array([find(x) for x in range(nf)]); r[~mask] = -1
    return r


def classify_shell(U, F, threshold=-0.2):
    fn = face_normals(U, F); fn /= np.maximum(np.linalg.norm(fn, axis=1), 1e-30)[:, None]
    cen = U[F].mean(1)
    zs = np.arange(U[:, 2].min(), U[:, 2].max() + 0.01, 0.01); cx = []; cy = []
    for z in zs:
        s = U[np.abs(U[:, 2] - z) < 0.006]
        cx.append((s[:, 0].min() + s[:, 0].max()) / 2 if len(s) else np.nan); cy.append((s[:, 1].min() + s[:, 1].max()) / 2 if len(s) else np.nan)
    cx = np.asarray(cx); cy = np.asarray(cy); ok = ~np.isnan(cx)
    c = np.stack([np.interp(cen[:, 2], zs[ok], cx[ok]), np.interp(cen[:, 2], zs[ok], cy[ok])], 1)
    rad = cen[:, :2] - c
    radial = np.c_[rad, np.zeros(len(c))] / (np.linalg.norm(rad, axis=1)[:, None] + 1e-12)
    d = np.sum(fn * radial, 1)
    pairs = face_adjacency(F)
    seed = int(np.argmax(np.linalg.norm(rad, axis=1)))
    allowed = d > threshold
    lab = components(len(F), pairs, allowed)
    outer = lab == lab[seed]
    comp = components(len(F), pairs, ~outer)
    ids, counts = np.unique(comp[comp >= 0], return_counts=True)
    require(len(ids) > 0, 'No inner wall found')
    main = ids[np.argmax(counts)]
    inner = comp == main
    return inner, dict(innerFaces=int(inner.sum()), outerFaces=int((~inner).sum()), strayPocketsReturnedToSkin=int(len(ids) - 1),
                       strayPocketFaces=int(counts.sum() - counts.max()))


def boundary_loops(F):
    ue, cnt = edges(F)
    b = ue[cnt == 1]
    # directed boundary edges from faces
    d = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    key = {tuple(sorted(x)) for x in map(tuple, b)}
    nxt = {}
    for a, c in d:
        if (min(a, c), max(a, c)) in key:
            nxt[int(a)] = int(c)
    loops = []; seen = set()
    for s in list(nxt):
        if s in seen:
            continue
        loop = [s]; seen.add(s); x = nxt[s]
        while x != s and x in nxt and x not in seen:
            loop.append(x); seen.add(x); x = nxt[x]
        loops.append(loop)
    return loops  # each loop follows the existing faces' edge direction


def resample_closed(points, count):
    P = np.asarray(points, float)
    seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1]
    t = np.linspace(0, total, count, endpoint=False)
    out = np.empty((count, P.shape[1]))
    for k in range(P.shape[1]):
        out[:, k] = np.interp(t, cum, np.concatenate([P[:, k], P[:1, k]]))
    return out


def zipper(outer_ids, outer_pts, inner_ids, inner_pts, centre):
    """Triangulate between two closed rings (same orientation) by advancing on angle about centre."""
    def ang(p):
        a = np.arctan2(p[:, 1] - centre[1], p[:, 0] - centre[0])
        return np.unwrap(a - a[0]) + a[0]
    ao = ang(outer_pts); ai = ang(inner_pts)
    # align start of inner ring to outer start
    shift = int(np.argmin(np.abs(((ai - ao[0] + np.pi) % (2 * np.pi)) - np.pi)))
    inner_ids = np.roll(inner_ids, -shift); inner_pts = np.roll(inner_pts, -shift, 0); ai = ang(inner_pts)
    if ai[0] > ao[0] + np.pi:
        ai -= 2 * np.pi
    sign = 1 if ao[-1] > ao[0] else -1
    ao_ext = np.concatenate([ao, [ao[0] + sign * 2 * np.pi]]); ai_ext = np.concatenate([ai, [ai[0] + sign * 2 * np.pi]])
    no, ni = len(outer_ids), len(inner_ids)
    i = j = 0; tris = []
    while i < no or j < ni:
        o0, o1 = outer_ids[i % no], outer_ids[(i + 1) % no]
        n0, n1 = inner_ids[j % ni], inner_ids[(j + 1) % ni]
        if j >= ni or (i < no and sign * ao_ext[i + 1] <= sign * ai_ext[j + 1]):
            tris.append((o0, o1, n0)); i += 1
        else:
            tris.append((o0, n1, n0)); j += 1
    return tris


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'Fresh descendant directory required')
    cfg = json.loads(a.config.read_text())
    master = Path(cfg['master']); require(sha(master) == cfg['masterSha256'], 'Parent changed')
    mesh = Mesh(master); desc = Descendant(mesh)
    U, F = mesh.U, mesh.F
    before = closure(F)
    inner, cls = classify_shell(U, F, cfg.get('outwardThreshold', -0.2))
    axis_xy = np.asarray(cfg['apertureAxisXY'], float)
    vz = U[:, 2]; vr = np.linalg.norm(U[:, :2] - axis_xy, axis=1)
    lip_v = (vz > cfg['lipCut']) & (vr < cfg['lipRadius'])
    lip = (~inner) & lip_v[F].any(1)
    remove = inner | lip
    # repair zone: drop the 1-ring of non-manifold edges and of degenerate tiny boundary loops so they become
    # simple holes that are fan-filled below
    repaired_faces = 0
    for _ in range(4):
        F1 = F[~remove]
        ue1, cnt1 = edges(F1)
        bad = set(np.unique(ue1[cnt1 > 2]).tolist())
        for l in boundary_loops(F1):
            if len(l) < cfg.get('degenerateLoopVertices', 5):
                bad.update(l)
        if not bad:
            break
        badv = np.zeros(len(U), bool); badv[list(bad)] = True
        ring = badv[F].any(1) & ~remove
        repaired_faces += int(ring.sum()); remove = remove | ring
    keepF = ~remove
    F1 = F[keepF]
    loops = boundary_loops(F1)
    sizes = sorted(len(l) for l in loops)
    neck = max(loops, key=len)
    require(len(neck) >= 24, 'Aperture loop not found')
    L = np.asarray(neck)
    B = U[L]
    centre = B[:, :2].mean(0)
    # wall tangent per loop vertex from kept lower neighbours
    ue, cnt = edges(F1)
    nbr = {}
    for x, y in ue:
        nbr.setdefault(int(x), []).append(int(y)); nbr.setdefault(int(y), []).append(int(x))
    inset = set(L.tolist())
    tang = []
    for v in L:
        low = [n for n in nbr.get(int(v), []) if n not in inset and U[n, 2] < U[v, 2]]
        d = U[v] - (U[low].mean(0) if low else U[v] - np.array([0, 0, 1.]))
        er = U[v, :2] - centre; er /= max(np.linalg.norm(er), 1e-9)
        t2 = np.array([np.dot(d[:2], er), d[2]]); t2 /= max(np.linalg.norm(t2), 1e-9)
        if t2[1] < 0.2:
            t2 = np.array([t2[0], 0.2]); t2 /= np.linalg.norm(t2)
        tang.append(t2)
    tang = np.asarray(tang)
    apex = cfg['apexZ']
    R = np.linalg.norm(B[:, :2] - centre, axis=1); er = (B[:, :2] - centre) / R[:, None]
    z0 = B[:, 2]
    a_len = cfg.get('tangentLength', 0.55) * np.maximum(apex - z0, 0.006)
    P0 = np.c_[R, z0]; P1 = P0 + a_len[:, None] * tang
    P2 = np.c_[cfg.get('apexShoulder', 0.45) * R, np.full_like(R, apex)]; P3 = np.c_[np.zeros_like(R), np.full_like(R, apex)]
    rings = cfg.get('rings', 10)
    U2 = list(U); newF = []
    prev_ids = L; prev_pts = B
    n0 = len(L)
    for k in range(1, rings):
        u = k / rings
        Q = ((1 - u) ** 3) * P0 + (3 * (1 - u) ** 2 * u) * P1 + (3 * (1 - u) * u * u) * P2 + (u ** 3) * P3
        pts = np.c_[centre + er * Q[:, :1], Q[:, 1]]
        count = max(12, int(round(n0 * (1 - u))))
        pts = resample_closed(pts, count)
        ids = np.arange(len(U2), len(U2) + count); U2.extend(pts)
        newF += zipper(prev_ids, prev_pts, ids, pts, centre)
        prev_ids, prev_pts = ids, pts
    apex_id = len(U2); U2.append(np.r_[centre, apex])
    for i in range(len(prev_ids)):
        newF.append((prev_ids[i], prev_ids[(i + 1) % len(prev_ids)], apex_id))
    newF = np.asarray(newF, np.int64)
    # orientation: loop L follows existing faces' direction a->b; new faces must contain b->a
    d0 = (L[0], L[1])
    f0 = newF[np.any(newF == L[0], 1) & np.any(newF == L[1], 1)][0]
    has_same = any((f0[k], f0[(k + 1) % 3]) == d0 for k in range(3))
    if has_same:
        newF = newF[:, [0, 2, 1]]
    U2 = np.asarray(U2)
    # owning primitive for the cap: the primitive of most skin faces on the loop
    loopset = np.zeros(len(U2), bool); loopset[L] = True
    adj_faces = np.flatnonzero(keepF)[loopset[F1].any(1)]
    cap_prim = int(np.bincount(mesh.face_prim[adj_faces]).argmax())
    prim = mesh.prims[cap_prim]
    uv_of = {}
    for vid, uv in zip(prim['vid'], prim['uv']):
        uv_of.setdefault(int(vid), uv)
    loop_uv = np.asarray([uv_of.get(int(v), np.array([0.5, 0.5])) for v in L])
    loop_ang = np.arctan2(B[:, 1] - centre[1], B[:, 0] - centre[0])
    for vid in range(len(U), len(U2)):
        an = np.arctan2(U2[vid, 1] - centre[1], U2[vid, 0] - centre[0])
        k = int(np.argmin(np.abs((loop_ang - an + np.pi) % (2 * np.pi) - np.pi)))
        desc.extra_uv[vid] = loop_uv[k]
    for v in L:
        if int(v) not in uv_of:
            desc.extra_uv[int(v)] = loop_uv[0]
    # assemble
    Fall = np.concatenate([F1, newF])
    face_prim = np.concatenate([mesh.face_prim[keepF], np.full(len(newF), cap_prim)])
    face_source = np.concatenate([np.flatnonzero(keepF), -np.ones(len(newF), np.int64)])
    # smoothing weights: cap 1, skin band cosine within blend of the loop
    w = np.zeros(len(U2))
    w[len(U):] = 1.0
    blend = cfg.get('blend', 0.02)
    dist = np.full(len(U2), np.inf)
    for s in range(0, len(U), 20000):
        dd = np.linalg.norm(U[s:s + 20000, None, :] - B[None, :, :], axis=2).min(1)
        dist[s:s + len(dd)] = dd
    used = np.zeros(len(U2), bool); used[np.unique(F1)] = True
    band = used & (dist < blend)
    w[band] = 0.5 * (1 + np.cos(np.pi * dist[band] / blend))
    w[L] = 1.0
    X = laplacian_smooth(U2, Fall, w, cfg.get('smoothIterations', 40), cfg.get('lambda', 0.5), cfg.get('mu', -0.53))
    # fill small residual holes (pinholes)
    extra = []
    filled = []
    for loop in boundary_loops(Fall):
        if len(loop) <= cfg.get('maxPinholeEdges', 24):
            c = len(X) + len(extra); extra.append(X[loop].mean(0))
            for i in range(len(loop)):
                extra_face = (loop[(i + 1) % len(loop)], loop[i], c)  # reversed relative to existing edge direction
                filled.append(extra_face)
            pf = np.flatnonzero(np.any(Fall == loop[0], 1))
            pp = int(face_prim[pf[0]])
            puv = {}
            for vid, uv in zip(mesh.prims[pp]['vid'], mesh.prims[pp]['uv']):
                puv.setdefault(int(vid), uv)
            desc.extra_uv[c] = puv.get(int(loop[0]), np.array([0.5, 0.5]))
            face_prim = np.concatenate([face_prim, np.full(len(loop), pp)])
            face_source = np.concatenate([face_source, -np.ones(len(loop), np.int64)])
    if extra:
        X = np.concatenate([X, np.asarray(extra)]); Fall = np.concatenate([Fall, np.asarray(filled, np.int64)])
    # remove vertices no longer referenced (inner wall) from the welded table by compaction
    usedv = np.zeros(len(X), bool); usedv[np.unique(Fall)] = True
    desc.U = X; desc.F = Fall; desc.face_prim = face_prim; desc.face_source = face_source
    after = closure(Fall)
    require(after['boundaryEdges'] == 0, 'Cap closure left open boundary edges: %d' % after['boundaryEdges'])
    a.output.mkdir(parents=True)
    out = a.output / (cfg.get('name', 'capped') + '-local.glb')
    built = desc.write(out)
    origin = np.asarray(cfg.get('worldOrigin', [0, 0, 0]), float)
    cap_pts = X[len(U):len(U2)]
    front = cap_pts[cap_pts[:, 1] > np.percentile(cap_pts[:, 1], 90)]
    record = dict(schemaVersion=1, kind='aperture-cap-descendant', part=cfg['part'], parent={'path': str(master), 'sha256': sha(master)},
                  descendant={'path': str(out), 'sha256': sha(out)}, config=cfg, configSha256=sha(a.config), helperSha256=sha(__file__),
                  classification=cls, lipFacesRemoved=int(lip.sum()), innerFacesRemoved=int(inner.sum()),
                  loopsAfterRemoval=sizes, apertureLoopVertices=int(len(L)), capPrimitive=cap_prim, capFaces=int(len(newF)),
                  pinholesFilled=int(len(extra)), nonManifoldRepairFacesRemoved=repaired_faces, closureBefore=before, closureAfter=after,
                  trianglesBefore=int(len(F)), trianglesAfter=int(len(Fall)),
                  capWorld={'apexZ': float(X[apex_id, 2] + origin[2]), 'loopZRange': [float(B[:, 2].min() + origin[2]), float(B[:, 2].max() + origin[2])],
                            'frontEdgeMinZ': float(front[:, 2].min() + origin[2]) if len(front) else None,
                            'capZRange': [float(cap_pts[:, 2].min() + origin[2]), float(cap_pts[:, 2].max() + origin[2])]},
                  maxDisplacementOfRetainedSkinMeters=float(np.linalg.norm(X[:len(U)][used[:len(U)]] - U[used[:len(U)]], axis=1).max()),
                  uvPolicy='Retained vertices keep exact UVs; cap/pinhole vertices take the nearest loop vertex UV (provisional until the material stage).',
                  policy='Topology changed only by removing the hidden inner wall/rolled lip and adding cap/pinhole faces; maps/materials exact; no approval implied.')
    write_receipt(a.output / 'descendant.json', record)
    shutil.copy2(__file__, a.output / 'executed-helper.py'); shutil.copy2(a.config, a.output / 'executed-config.json')
    print(json.dumps({k: record[k] for k in ('classification', 'lipFacesRemoved', 'loopsAfterRemoval', 'capFaces', 'pinholesFilled', 'closureAfter', 'capWorld',
                                                'trianglesBefore', 'trianglesAfter', 'maxDisplacementOfRetainedSkinMeters')}, default=str))


if __name__ == '__main__':
    main()
