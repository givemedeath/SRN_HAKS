"""Matched orthographic clay views of fitted heads in their shared NWN head_g frame."""
from contextlib import ExitStack
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image, ImageDraw

from headkit.body_neck import mesh_parts
from headkit.common import pin, read, verify
from headkit.diagnostics import sheet
from headkit.gltf import positions
from headkit.mesh import BASIS
from headkit.rays import EmbreeScene
from headkit.neck import body_neck as read_body_neck


def attempt_result(head, attempt):
    if not re.fullmatch(r'attempt-[0-9]+', attempt):
        raise ValueError('An explicit fit attempt is required')
    receipt = pin(head/'run/fit'/attempt/'receipt.json')
    data = read(receipt['path'])
    if data.get('state') != 'complete':
        raise ValueError('A complete fit attempt is required')
    return receipt, data['result']


def bounds(vertices, matrix):
    # Only the extrema of three projections are needed, even for a multimegabyte mesh.
    axes = matrix[:3, :3]
    extrema = []
    for axis, offset in zip(axes, matrix[:3, 3]):
        projected = vertices @ axis.astype(np.float32) + offset
        extrema.append([projected.min(), projected.max()])
    return np.asarray(extrema).T


def surface(model, toward, origins, light, tint, normals=None, texture=None):
    scene, vertices, faces, matrix = model
    inverse = np.linalg.inv(matrix)
    direction = inverse[:3, :3] @ -toward
    depths, ids, _ = scene.query(origins @ inverse[:3, :3].T + inverse[:3, 3], direction/np.linalg.norm(direction))
    hit = ids >= 0
    tri = vertices[faces[ids[hit]]]
    ab, ac = tri[:,1]-tri[:,0], tri[:,2]-tri[:,0]
    normal = np.cross(ab, ac)
    if (normals is not None or texture is not None) and hit.any():
        # Interpolate the GLB's saved corner normals at the actual ray hit.
        world_hits = origins[hit] - toward*(depths[hit]/np.linalg.norm(direction))[:,None]
        local_hits = world_hits @ inverse[:3,:3].T + inverse[:3,3]
        delta = local_hits - tri[:,0]
        denom = np.einsum('ij,ij->i', normal, normal)
        w1 = np.einsum('ij,ij->i', np.cross(delta, ac), normal) / np.maximum(denom, 1e-30)
        w2 = np.einsum('ij,ij->i', np.cross(ab, delta), normal) / np.maximum(denom, 1e-30)
        weights = np.column_stack((1-w1-w2, w1, w2))
        if texture is not None:
            uv, pixels = texture
            st = np.einsum('ij,ijk->ik', weights, uv[ids[hit]])
            rgb = np.full((len(origins), 3), 36, np.uint8)
            h, w = pixels.shape[:2]
            xy = np.clip(st * [w,h] - .5, [0,0], [w-1,h-1])
            x, y = np.floor(xy).astype(int).T
            x1, y1 = np.minimum(x+1,w-1), np.minimum(y+1,h-1)
            fx, fy = (xy - np.floor(xy)).T[:,:,None]
            rgb[hit] = np.rint((1-fy)*((1-fx)*pixels[y,x]+fx*pixels[y,x1]) +
                                fy*((1-fx)*pixels[y1,x]+fx*pixels[y1,x1])).astype(np.uint8)
            return depths/np.linalg.norm(direction), rgb
        normal = np.einsum('ij,ijk->ik', weights, normals[faces[ids[hit]]])
    normal = normal @ inverse[:3, :3]
    normal /= np.maximum(np.linalg.norm(normal, axis=1)[:, None], 1e-12)
    lighting = normal @ light
    # Fit silhouettes may be two-sided; a saved-normal repair review must expose inversions.
    lighting = np.abs(lighting) if normals is None else np.maximum(lighting, 0)
    shade = np.clip(.24+.75*lighting, 0, 1)
    rgb = np.full((len(origins), 3), 36, np.uint8)
    rgb[hit] = (shade[:, None]*np.asarray(tint)).astype(np.uint8)
    return depths/np.linalg.norm(direction), rgb


def tile(model, toward, center, span, size, ruler, neck=None, normals=None, texture=None):
    yy, xx = np.mgrid[0:size, 0:size]
    dx = ((xx.ravel()+.5)/size-.5)*span
    dz = (.5-(yy.ravel()+.5)/size)*span
    right = np.cross([0., 0., 1.], toward)
    right /= np.linalg.norm(right)
    up = np.cross(toward, right)
    origins = center + toward*span*2 + dx[:, None]*right + dz[:, None]*up
    light = .90*toward - .18*right + .39*up
    depth, rgb = surface(model, toward, origins, light, [230,225,220], normals, texture)
    if neck is not None:
        other_depth, other_rgb = surface(neck, toward, origins, light, [105,174,200])
        nearer = other_depth < depth
        rgb[nearer] = other_rgb[nearer]
    im = Image.fromarray(rgb.reshape(size, size, 3))
    if ruler:
        draw = ImageDraw.Draw(im)
        for mm in range(int(1000*(center[2]-span/2))//20*20, int(1000*(center[2]+span/2))+1, 20):
            row = round(size*(.5-(mm/1000-center[2])/span)-.5)
            if 6 <= row < size-6:
                draw.line((0,row,7,row), fill='#78aeca')
                draw.text((9,row-6), str(mm), fill='#9ac4da')
                draw.line((size-8,row,size-1,row), fill='#78aeca')
    return im


def compare(head, attempts, output, reference=False, with_neck=False):
    head, output = Path(head).resolve(), Path(output)
    if len(attempts) != (1 if reference else 2):
        raise ValueError('Supply one attempt for the bound reference or two attempts for a pose comparison')
    records = [attempt_result(head, attempt) for attempt in attempts]
    fits = [result for _, result in records]
    if any(f['source'] != fits[0]['source'] or f['reference'] != fits[0]['reference'] for f in fits):
        raise ValueError('Compare fits of the same head and reference')
    embree = read(head/'bindings.json')['embree']
    pins = [receipt for receipt,_ in records] + [fits[0]['source'], fits[0]['reference'], embree]
    verify(pins, fresh=True)
    vertices, faces = positions(fits[0]['source']['path'])
    models = []
    labels = []
    with ExitStack() as stack:
        def scene(v, f):
            item = EmbreeScene(embree['path'], v.astype(np.float32,copy=False), f.astype(np.uint32,copy=False))
            stack.callback(item.close)
            return item
        if reference:
            mdl = Path(fits[0]['reference']['path'])
            geometry = re.split(r'(?im)^\s*(?:endmodelgeom|newanim)\b', mdl.read_text(encoding='utf-8'), maxsplit=1)[0]
            rv, rf = mesh_parts(geometry)
            models.append((scene(rv, rf), rv, rf, np.eye(4)))
            labels.append('Bound fit reference')
        source = scene(vertices, faces)
        for name, fit in zip(attempts, fits):
            models.append((source, vertices, faces, np.asarray(fit['matrix']) @ BASIS))
            degrees = fit.get('pitch', {}).get('chinDownDegrees', 0)
            labels.append(f'{name}   {degrees:g} deg   {fit["scale"]/fits[0]["scale"]:.2f}x' if not reference else name)
        neck = None
        if with_neck:
            manifest = pin(head/'manifest.json')
            bound = read(manifest['path'])['inputs']['bodyNeck']
            body = {'path':str(head/bound['path']), 'sha256':bound['sha256']}
            pins.extend([manifest,body])
            verify([body], fresh=True)
            nv, nf = read_body_neck(body['path'])
            neck = (scene(nv,nf), nv,nf,np.eye(4))
        extents = np.vstack([bounds(v, m) for _,v,_,m in models + ([neck] if neck else [])])
        low, high = extents.min(axis=0), extents.max(axis=0)
        center = (low+high)/2
        span = max((high-low)[2], np.linalg.norm((high-low)[:2]))*1.10
        views = [('Side', (1.,0.,0.)), ('Three-quarter', (.78,.625,0.))]
        if reference:
            views = [('Front', (0.,1.,0.)), ('Side', (1.,0.,0.))]
        if with_neck:
            views.extend([('Rear', (0.,-1.,0.)), ('Below jaw', (.65,.75,-.55))])
        size = 320 if with_neck else 480 if reference else 384
        tiles = []
        for label, direction in views:
            toward = np.array(direction) / np.linalg.norm(direction)
            for name, model in zip(labels, models):
                caption = '   |   blue = body neck' if with_neck else '   |   height in mm' if reference else ''
                tiles.append((f'{name}   {label}'+caption, tile(model, toward, center, span, size, reference and not with_neck, neck)))
        if with_neck:
            tiles = tiles[::2]+tiles[1::2]
    with TemporaryDirectory(dir=output.parent) as scratch:
        candidate = Path(scratch)/'comparison.png'
        sheet(tiles, candidate, size, columns=len(views) if with_neck else len(models))
        verify(pins, fresh=True)
        candidate.replace(output)
    print(output)
