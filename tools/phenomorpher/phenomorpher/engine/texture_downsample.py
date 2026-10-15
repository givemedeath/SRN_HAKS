"""Integer 2:1 area reduction of body palettes, normal maps and roughness maps to a size cap.

Names, formats, orientation, headers (except dimensions), footers and materials are kept.
PLT: per 2x2 block the coverage-mode layer wins (ties: skin 0, cloth 4/5, then lowest id);
intensity is the mean of the winning layer's texels. Normal: RG decoded to a unit vector with
the shader's reconstructed Z, averaged, renormalized and re-encoded (no green flip, Z >= 0.02).
Roughness: linear per-channel mean. Each unique payload is converted once.
"""
import hashlib
import json
import re
import struct
from pathlib import Path

import numpy as np

KIND = 'PhenoMorpher-texture-downsample'
SLOTS = {'texture1': 'normal', 'texture3': 'roughness'}
LAYERS = 10


def digest(data):
    return hashlib.sha256(data).hexdigest()


def mean_round(total, count):
    """Integer mean, ties to even, so repeated reductions add no brightness bias."""
    quotient, remainder = np.divmod(np.asarray(total), np.asarray(count))
    twice = 2*remainder
    return quotient + ((twice > count) | ((twice == count) & (quotient % 2 == 1)))


def blocks(array):
    h, w = array.shape[:2]
    if h % 2 or w % 2:
        raise ValueError('Even texture dimensions required')
    return array.reshape(h//2, 2, w//2, 2, *array.shape[2:]).swapaxes(1, 2).reshape(h//2, w//2, 4, *array.shape[2:])


def layer_rank(layer):
    # Tie order: skin 0, then cloth 4/5, then every other layer; lowest id within a group.
    group = np.where(layer == 0, 0, np.where((layer == 4) | (layer == 5), 1, 2))
    return group*LAYERS + layer


def reduce_plt(data):
    if data[:8] != b'PLT V1  ':
        raise ValueError('PLT header required')
    width, height = struct.unpack_from('<II', data, 16)
    if len(data) != 24 + width*height*2:
        raise ValueError('PLT payload size differs from header')
    pixels = np.frombuffer(data, np.uint8, offset=24).reshape(height, width, 2)
    if pixels[..., 1].max() >= LAYERS:
        raise ValueError('PLT layer outside 0-9')
    quad = blocks(pixels); intensity = quad[..., 0].astype(np.int64); layer = quad[..., 1].astype(np.int64)
    counts = np.stack([(layer == k).sum(-1) for k in range(LAYERS)], -1)
    # Highest count wins; among equal counts the lowest rank key wins.
    key = counts*100 - layer_rank(np.arange(LAYERS))
    winner = key.argmax(-1); chosen = layer == winner[..., None]
    value = mean_round((intensity*chosen).sum(-1), chosen.sum(-1))
    out = np.stack([value, winner], -1).astype(np.uint8)
    header = bytearray(data[:24]); struct.pack_into('<II', header, 16, width//2, height//2)
    mixed = (counts > 0).sum(-1) > 1
    pairs = {}
    for w, present in zip(winner[mixed], counts[mixed] > 0):
        for other in np.nonzero(present)[0]:
            if other != w:
                pairs[f'{int(other)}->{int(w)}'] = pairs.get(f'{int(other)}->{int(w)}', 0) + 1
    before = np.bincount(pixels[..., 1].ravel(), minlength=LAYERS); after = np.bincount(winner.ravel(), minlength=LAYERS)*4
    stats = {'layerTexelsBefore': before.tolist(), 'layerTexelsAfterTimesFour': after.tolist(),
             'mixedBlocks': int(mixed.sum()), 'mixedBlockWinners': dict(sorted(pairs.items())),
             'intensityMeanByLayerBefore': {int(k): float(pixels[..., 0][pixels[..., 1] == k].mean()) for k in np.nonzero(before)[0]},
             'intensityMeanByLayerAfter': {int(k): float(out[..., 0][winner == k].mean()) for k in np.nonzero(after)[0]}}
    return bytes(header) + out.tobytes(), stats


def tga_parts(data):
    id_length = data[0]; width, height, depth, descriptor = struct.unpack_from('<HHBB', data, 12)
    if data[1] != 0 or data[2] != 2 or depth != 24:
        raise ValueError('Uncompressed 24-bit TGA required')
    offset = 18 + id_length; count = width*height*3
    pixels = np.frombuffer(data, np.uint8, offset=offset, count=count).reshape(height, width, 3)
    return data[:offset], pixels, data[offset+count:]


def tga_join(head, pixels, tail):
    head = bytearray(head); struct.pack_into('<HH', head, 12, pixels.shape[1], pixels.shape[0])
    return bytes(head) + np.ascontiguousarray(pixels).tobytes() + tail


def decode_normals(bgr):
    x = bgr[..., 2]/255*2-1; y = bgr[..., 1]/255*2-1
    z = np.sqrt(np.maximum(1-x*x-y*y, 0))
    return np.stack([x, y, z], -1)


def reduce_normal(data):
    head, pixels, tail = tga_parts(data)
    mean = blocks(decode_normals(pixels.astype(float))).mean(2); length = np.linalg.norm(mean, axis=-1)
    unit = mean/np.maximum(length, 1e-12)[..., None]
    unit[..., 2] = np.maximum(unit[..., 2], 0.02); unit /= np.linalg.norm(unit, axis=-1)[..., None]
    rgb = np.clip(np.round((unit*0.5+0.5)*255), 0, 255).astype(np.uint8)
    out = rgb[..., ::-1]
    decoded = decode_normals(out.astype(float))
    stats = {'averagedLengthMin': float(length.min()), 'averagedLengthP01': float(np.percentile(length, 1)),
             'storedBlueMeanBefore': float(pixels[..., 0].mean()), 'storedBlueMeanAfter': float(out[..., 0].mean()),
             'reconstructedZMinAfter': float(decoded[..., 2].min()),
             'encodedLengthErrorMax': float(np.abs(np.linalg.norm((out[..., ::-1]/255*2-1), axis=-1)-1).max())}
    return tga_join(head, out, tail), stats


def reduce_roughness(data):
    head, pixels, tail = tga_parts(data)
    out = mean_round(blocks(pixels.astype(np.int64)).sum(2), 4).astype(np.uint8)
    stats = {'channelMeanBefore': pixels.reshape(-1, 3).mean(0).tolist(), 'channelMeanAfter': out.reshape(-1, 3).mean(0).tolist(),
             'channelMinMaxBefore': [int(pixels.min()), int(pixels.max())], 'channelMinMaxAfter': [int(out.min()), int(out.max())]}
    return tga_join(head, out, tail), stats


def size(data, suffix):
    if suffix == '.plt':
        return struct.unpack_from('<II', data, 16)
    return struct.unpack_from('<HH', data, 12)


def map_kinds(root, manifest):
    """Normal/roughness role of every map from the MTR slot that names it."""
    kinds = {}
    for row in manifest['resources']:
        if row['role'] != 'selected-material':
            continue
        text = (root/row['path']).read_text(encoding='cp1252')
        for slot, name in re.findall(r'(?mi)^\s*(texture\d)\s+(\S+)', text):
            kind = SLOTS.get(slot.lower())
            if kind:
                previous = kinds.setdefault(name.lower(), kind)
                if previous != kind:
                    raise ValueError('Map used as both normal and roughness: ' + name)
    return kinds


def downsample(root, manifest_path, output, max_size=1024):
    root = Path(root).resolve(); output = Path(output)
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    output.mkdir(parents=True, exist_ok=False); kinds = map_kinds(root, manifest)
    payloads = {}; rows = []
    for row in manifest['resources']:
        if row['role'] not in ('selected-palette', 'selected-map'):
            continue
        path = root/row['path']; data = path.read_bytes(); suffix = path.suffix.lower()
        if digest(data) != row['sha256']:
            raise ValueError('Texture differs from the manifest: ' + row['path'])
        width, height = size(data, suffix)
        if max(width, height) <= max_size:
            continue
        if suffix == '.plt':
            kind = 'palette'
        elif suffix == '.tga':
            kind = kinds.get(path.stem.lower())
            if kind is None:
                raise ValueError('Map role unknown (no material slot): ' + row['path'])
        else:
            raise ValueError('Unsupported texture format: ' + row['path'])
        if row['sha256'] not in payloads:
            reduce = {'palette': reduce_plt, 'normal': reduce_normal, 'roughness': reduce_roughness}[kind]
            result, stats = data, None
            while max(size(result, suffix)) > max_size:
                result, stats = reduce(result)
            payloads[row['sha256']] = {'kind': kind, 'data': result, 'stats': stats, 'resources': []}
        entry = payloads[row['sha256']]
        if entry['kind'] != kind:
            raise ValueError('One payload used with two map roles: ' + row['path'])
        target = output/row['path']; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(entry['data'])
        entry['resources'].append(row['path'])
        new_width, new_height = size(entry['data'], suffix)
        rows.append({'path': row['path'], 'kind': kind, 'sourceSHA256': row['sha256'], 'sourceBytes': row['bytes'],
                     'source': [width, height], 'output': [new_width, new_height],
                     'sha256': digest(entry['data']), 'bytes': len(entry['data'])})
    receipt = {'schemaVersion': 1, 'kind': KIND, 'maxSize': max_size, 'resources': rows,
               'payloads': {sha: {'kind': p['kind'], 'outputSHA256': digest(p['data']), 'resources': p['resources'], 'stats': p['stats']}
                            for sha, p in payloads.items()},
               'summary': {'resources': len(rows), 'uniquePayloads': len(payloads),
                           'bytesBefore': sum(r['sourceBytes'] for r in rows), 'bytesAfter': sum(r['bytes'] for r in rows)},
               'assetApprovalCreated': False}
    (output/'downsample-receipt.json').write_text(json.dumps(receipt, indent=1)+'\n', encoding='utf-8', newline='\n')
    return receipt
