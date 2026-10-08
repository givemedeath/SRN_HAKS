"""Write one bounded positional/normal descendant (archive, candidate GLB, geometry receipt) of a sealed part.

Optional generator: female limb crease fairing (fair_female_limb_creases) inside a declared band; every moved
vertex must lie inside the declared position envelope. Normals/tangents follow bounded_descendant_rules (unit
normals; transport by the smoothed-geometric-normal rotation; optional declared smoothing regions). The candidate
GLB is the parent GLB with only POSITION/NORMAL/TANGENT bytes (and POSITION min/max) rewritten to float32 of the
new values. Verification is separate (diagnostic_bounded_descendant_representation). No approval implied.
"""
from pathlib import Path
import argparse, hashlib, json, struct, time
import numpy as np
import diagnostic_descendant_representation as base
import diagnostic_bounded_descendant_representation as rep
import fair_female_limb_creases as fair
import bounded_descendant_rules as rules

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
pin = lambda p: {'path': str(Path(p).resolve()), 'sha256': sha(p)}


def vertex_values(prim, vert, corners, primitive, count):
    """Per-GLB-vertex float32 values; every corner referencing a vertex must agree after float32 rounding."""
    m = prim.reshape(-1) == primitive; v = vert.reshape(-1)[m]; x = corners.reshape(-1, corners.shape[-1])[m].astype(np.float32)
    out = np.full((count, x.shape[1]), np.nan, np.float32); out[v] = x
    if not np.array_equal(out[v], x):
        raise ValueError('Corners sharing a GLB vertex disagree after float32 rounding')
    return out


def write_glb(parent_path, out_path, prim, vert, values):
    doc, binary = base.read_glb(parent_path); binary = bytearray(binary)
    for k, p in enumerate(doc['meshes'][0]['primitives']):
        for name, corners in values.items():
            if name not in p['attributes']:
                continue
            off, stride, width, count = rep.attribute_span(doc, k, name)
            old = base.accessor(doc, bytes(binary), p['attributes'][name])
            new = vertex_values(prim, vert, corners, k, count)
            unused = np.isnan(new).any(1); new[unused] = old[unused]
            for j in range(count):
                binary[off + j * stride: off + j * stride + 4 * width] = new[j].astype('<f4').tobytes()
            if name == 'POSITION':
                a = doc['accessors'][p['attributes'][name]]; a['min'] = [float(x) for x in new.min(0)]; a['max'] = [float(x) for x in new.max(0)]
    js = json.dumps(doc, separators=(',', ':')).encode(); js += b' ' * (-len(js) % 4); binary = bytes(binary) + b'\0' * (-len(binary) % 4)
    data = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(binary)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(binary), 0x004E4942) + binary
    Path(out_path).write_bytes(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--config', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False); cfg = json.loads(a.config.read_text(encoding='utf-8')); t0 = time.time()
    if cfg.get('kind') != 'bounded-descendant-generation-v1':
        raise ValueError('Explicit bounded descendant generation config required')
    rp, _ = base.checked_pin(cfg['parentReceipt']); g0 = json.loads(Path(rp).read_text(encoding='utf-8')); part = cfg['part']
    if g0['part'] != part or g0['coordinateSpace'] != 'working' or g0['statureApplications'] != 0:
        raise ValueError('Working parent receipt for the declared part required')
    cand = base.checked_pin({'path': g0['candidate'], 'sha256': g0['candidateSha256']})[0]; arch = base.checked_pin(g0['nativeCornerArchive'])[0]
    S = dict(np.load(arch, allow_pickle=False)); op = cfg['operation']; P0, N0 = S['positions'], S['normals']
    record = {}
    fairing = op['generator'].get('fairing')
    if fairing:
        U, F = fair.weld(P0); X, w, hist = fair.fair(U, F, fairing); P1 = fair.child_corners(P0, U, X, F)
        record['fairing'] = {'history': hist, 'bandVertices': int((w > 0).sum())}
    else:
        P1 = P0.copy()
    pdoc, pbin = base.read_glb(cand); prim, vert, praw = rep.glb_corners(pdoc, pbin)
    trows, glb_t = rep.glb_tangent_rows(prim, praw['tangents'])
    N1, T1, G1, report = rep.replay(P0, N0, P1, op, S, glb_t, trows)
    A = dict(S); A['positions'] = np.ascontiguousarray(P1, np.float64); A['normals'] = np.ascontiguousarray(N1, np.float64)
    if T1 is not None:
        A['tangents'] = np.ascontiguousarray(T1, np.float64)
    archive = out / 'native-corners.npz'; np.savez(archive, **A)
    values = {'POSITION': rep.to_gltf(A['positions']), 'NORMAL': rep.to_gltf(A['normals'])}
    if G1 is not None:
        full = np.zeros(P0.shape[:2] + (4,)); full[trows] = np.concatenate([rep.to_gltf(G1[..., :3]), G1[..., 3:]], axis=-1)
        values['TANGENT'] = full
    candidate = out / 'candidate-local.glb'; write_glb(cand, candidate, prim, vert, values)
    receipt = {k: g0[k] for k in ('schemaVersion', 'kind', *rep.IDENTITY)}
    receipt.update({k: g0[k] for k in rep.CARRIED if k in g0})
    receipt.update({'operation': rep.OPERATION, 'boundedDescendant': op, 'source': str(Path(cand)), 'sourceSha256': sha(cand), 'sourceReceipt': str(Path(rp)), 'sourceReceiptSha256': sha(rp),
                    'candidate': str(candidate), 'candidateSha256': sha(candidate), 'nativeCornerArchive': pin(archive), 'nativeCornerArchiveAuthority': 'native-f64',
                    'normalRuleReport': report, 'generatorReport': record, 'frozenInputs': {str(Path(p).resolve()): sha(p) for p in (rp, cand, arch, a.config, __file__, rep.__file__, rules.__file__, fair.__file__)},
                    'sourceFieldRepresentationsPreservedSeparately': True, 'runtimeSelected': False, 'nativeAccepted': False, 'productionAccepted': False})
    (out / 'geometry.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'part': part, 'receipt': pin(out / 'geometry.json'), 'normalRule': report, 'generator': record, 'seconds': round(time.time() - t0, 1)}))


if __name__ == '__main__':
    main()
