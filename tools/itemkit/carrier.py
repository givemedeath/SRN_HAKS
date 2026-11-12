"""Measure an installed stock melee carrier: where the hand holds it and how long it is.

A new family needs its native grip origin before any design can be fitted to it. The stock model's origin is the
attachment point in the hand, and the handle runs along +Y. The measured origin is the centre of the handle around
the hand: the middle of the narrow run that contains Y=0 when that run is short (a sword's hilt between pommel and
guard: within 1.6 usable lengths for one hand, 2 for two), else the origin itself (a haft much longer than the
hands). On the installed longsword this gives Y -0.037 against the reviewed -0.031, on the greatsword -0.071
against the Katana's measured -0.063. This measures; the both-body hand-fit review of
the first design on the carrier still approves it.
"""
from pathlib import Path
import struct
import numpy as np
from tools.headkit.common import require

SLICE = .005          # metres along Y
NARROW = 1.35         # a handle slice is at most this many times the narrowest section near the hand


def decode_stock(path):
    """(positions, faces) of every mesh in one stock binary model part, with rigid transforms applied."""
    from tools.headkit.native_reader import decode
    raw = Path(path).read_bytes(); offset = 20
    require(len(raw) > offset + 32 and struct.unpack_from('<I', raw, 0)[0] == 0, 'Binary NWN model required')
    name = raw[offset:offset + 32].split(b'\0')[0].decode('ascii')
    meshes = decode(raw, name, require_tangents=False, allow_constant_alpha=True, apply_rigid_transforms=True)
    require(meshes, 'Stock model has no mesh')
    positions, faces, base = [], [], 0
    for m in meshes:
        v = np.asarray(m['position'], float).reshape(-1, 3); positions.append(v)
        faces.append(np.asarray(m['faces'], np.int64).reshape(-1, 3) + base); base += len(v)
    return np.concatenate(positions), np.concatenate(faces)


def assemble(parts):
    """One (positions, faces) from several decoded parts."""
    positions, faces, base = [], [], 0
    for v, f in parts: positions.append(v); faces.append(f + base); base += len(v)
    return np.concatenate(positions), np.concatenate(faces)


def _section(tri, y):
    hits = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        v, w = tri[:, a], tri[:, b]; crossing = (v[:, 1] - y) * (w[:, 1] - y) < 0; v, w = v[crossing], w[crossing]
        if len(v): hits.extend(v + (w - v) * ((y - v[:, 1]) / (w[:, 1] - v[:, 1]))[:, None])
    return np.asarray(hits)


def measure(positions, faces, usable_length, hold='one'):
    """Grip origin, handle run and overall span of an assembled stock carrier (native metres, +Y toward the head)."""
    p = np.asarray(positions, float); require(p.ndim == 2 and p.shape[1] == 3 and len(p) >= 8, 'Stock carrier positions required')
    tri = p[np.asarray(faces, np.int64)]
    lo, hi = float(p[:, 1].min()), float(p[:, 1].max()); require(lo < 0 < hi, 'The stock hand point must lie on the carrier')
    edges = np.arange(lo, hi + SLICE, SLICE); width = np.full(len(edges) - 1, np.nan); centre = np.full((len(edges) - 1, 2), np.nan)
    for i in range(len(edges) - 1):
        s = _section(tri, (edges[i] + edges[i + 1]) / 2)
        if len(s) >= 3: width[i] = np.ptp(s[:, [0, 2]], axis=0).max(); centre[i] = (s[:, [0, 2]].min(0) + s[:, [0, 2]].max(0)) / 2
    hand = int(np.searchsorted(edges, 0.) - 1); near = np.arange(max(0, hand - 4), min(len(width), hand + 5))
    require(np.isfinite(width[near]).any(), 'No stock surface at the hand point')
    floor = float(np.nanmin(width[near])); narrow = np.isfinite(width) & (width <= NARROW * floor)
    a = hand
    while a > 0 and (narrow[a - 1] or not np.isfinite(width[a - 1])): a -= 1
    b = hand
    while b < len(width) - 1 and (narrow[b + 1] or not np.isfinite(width[b + 1])): b += 1
    run = [float(edges[a]), float(edges[b + 1])]; length = run[1] - run[0]
    hilt = (1.6 if hold == 'one' else 2.0) * usable_length    # a two-hand hilt holds both hands
    y = (run[0] + run[1]) / 2 if length <= hilt else 0.
    k = int(np.clip(np.searchsorted(edges, y) - 1, 0, len(width) - 1)); xz = centre[k] if np.isfinite(centre[k]).all() else np.nanmean(centre[near], 0)
    return {'gripOrigin': [float(xz[0]), float(y), float(xz[1])], 'handleRun': run, 'handleRunLength': length,
            'method': 'hilt-centre' if length <= hilt else 'hand-point', 'span': [lo, hi], 'length': hi - lo,
            'handleWidth': floor}
