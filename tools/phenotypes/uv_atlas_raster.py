"""Deterministic UV-atlas rasterization for single-PLT part checks and LEAN map tools.

Pixel centres are sampled (x right, y down, centre at i+0.5); native/ASCII texture V is bottom-up, so a UV maps to
pixel (u*W, (1-v)*H). The last face written wins. Pure numpy; no Blender, no client.
"""
import numpy as np


def uv_to_pixels(uv, width, height):
    uv = np.asarray(uv, dtype=np.float64)
    return np.stack([uv[:, 0]*width, (1-uv[:, 1])*height], 1)


def raster(points, faces, width, height, chunk_pixels=4_000_000):
    """Face-id (H,W int32, -1 empty) and barycentric (H,W,3 float32) buffers of pixel-space triangles."""
    faceid = np.full((height, width), -1, np.int32); bary = np.zeros((height, width, 3), np.float32)
    faces = np.asarray(faces, dtype=np.int64)
    if not len(faces):
        return faceid, bary
    T = np.asarray(points, dtype=np.float64)[faces]
    lo = np.clip(np.floor(T.min(1)-0.5).astype(np.int64), 0, [width-1, height-1])
    hi = np.clip(np.ceil(T.max(1)-0.5).astype(np.int64), 0, [width-1, height-1])
    w = hi[:, 0]-lo[:, 0]+1; h = hi[:, 1]-lo[:, 1]+1
    inside = (T.max(1) >= 0).all(1) & (T.min(1)[:, 0] <= width) & (T.min(1)[:, 1] <= height)
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    den = (b[:, 1]-c[:, 1])*(a[:, 0]-c[:, 0])+(c[:, 0]-b[:, 0])*(a[:, 1]-c[:, 1])
    counts = np.where(inside & (np.abs(den) > 1e-14), w*h, 0)
    cum = np.cumsum(counts); n = len(faces); i0 = 0
    while i0 < n:
        i1 = int(np.searchsorted(cum, (cum[i0-1] if i0 else 0)+chunk_pixels, 'right')); i1 = min(max(i1, i0+1), n)
        cc = counts[i0:i1]; total = int(cc.sum())
        if total:
            idx = np.repeat(np.arange(i0, i1), cc); start = np.repeat(np.cumsum(cc)-cc, cc); k = np.arange(total)-start
            px = lo[idx, 0]+k % w[idx]; py = lo[idx, 1]+k//w[idx]; x = px+0.5; y = py+0.5
            l0 = ((b[idx, 1]-c[idx, 1])*(x-c[idx, 0])+(c[idx, 0]-b[idx, 0])*(y-c[idx, 1]))/den[idx]
            l1 = ((c[idx, 1]-a[idx, 1])*(x-c[idx, 0])+(a[idx, 0]-c[idx, 0])*(y-c[idx, 1]))/den[idx]
            l2 = 1-l0-l1; inner = (l0 >= -1e-7) & (l1 >= -1e-7) & (l2 >= -1e-7)
            faceid[py[inner], px[inner]] = idx[inner]
            bary[py[inner], px[inner]] = np.stack([l0[inner], l1[inner], l2[inner]], 1)
        i0 = i1
    return faceid, bary


def coverage(uv, faces, width, height):
    """Boolean texel coverage of UV triangles (native bottom-up V)."""
    faceid, _ = raster(uv_to_pixels(uv, width, height), faces, width, height)
    return faceid >= 0


def dilate4(mask, radius):
    """4-neighbour binary dilation repeated `radius` times (no wrap)."""
    mask = np.asarray(mask, bool).copy()
    for _ in range(int(radius)):
        grown = mask.copy(); grown[1:] |= mask[:-1]; grown[:-1] |= mask[1:]; grown[:, 1:] |= mask[:, :-1]; grown[:, :-1] |= mask[:, 1:]
        mask = grown
    return mask
