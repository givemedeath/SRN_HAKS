"""Apply a declared pelvis skin shade offset; preserve all geometry and other resources.

This is a native material descendant, not a new generator/source-map assertion.
The calibration uses frozen native UV samples and the installed skin palette.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

import numpy as np
from PIL import Image


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def adjust_plt(data, offset):
    require(data[:8] == b'PLT V1  ' and len(data) >= 24, 'Invalid PLT V1 header')
    layers, reserved, width, height = struct.unpack_from('<IIII', data, 8)
    require(layers == 10 and reserved == 0 and width > 0 and height > 0,
            'Unsupported PLT dimensions/header fields')
    require(len(data) == 24 + width * height * 2, 'PLT payload length mismatch')
    require(isinstance(offset, int) and -255 <= offset <= 255 and offset != 0,
            'Offset must be a nonzero integer in [-255,255]')
    original = np.frombuffer(data, np.uint8, offset=24).reshape(height, width, 2)
    require(np.all(original[:, :, 1] < layers), 'Invalid PLT layer index')
    changed = original.copy()
    skin = original[:, :, 1] == 0
    raw = original[:, :, 0].astype(np.int16) + offset
    clamped = skin & ((raw < 0) | (raw > 255))
    changed[:, :, 0][skin] = np.clip(raw[skin], 0, 255).astype(np.uint8)
    result = data[:24] + changed.tobytes()
    require(result[:24] == data[:24], 'Header changed')
    require(np.array_equal(changed[:, :, 1], original[:, :, 1]), 'Layer bytes changed')
    require(np.array_equal(changed[~skin], original[~skin]), 'Other layers changed')
    return result, original[::-1], changed[::-1], clamped[::-1]


def taps(image, uv):
    height, width = image.shape
    require(np.isfinite(uv).all(), 'Nonfinite native UV')
    q = np.clip(uv, 0, 1)
    x = q[:, 0] * (width - 1)
    y = (1 - q[:, 1]) * (height - 1)
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - ix, y - iy
    xx = np.stack([ix, np.minimum(ix + 1, width - 1), ix, np.minimum(ix + 1, width - 1)], 1)
    yy = np.stack([iy, iy, np.minimum(iy + 1, height - 1), np.minimum(iy + 1, height - 1)], 1)
    weight = np.stack([(1-fx)*(1-fy), fx*(1-fy), (1-fx)*fy, fx*fy], 1)
    return image[yy, xx], weight, yy, xx


def stats(values, areas, mask, palette):
    v = values[mask].reshape(-1)
    w = np.repeat(areas[mask] / values.shape[1], values.shape[1])
    require(w.sum() > 0, 'Empty/zero-area calibration group')
    mean = float(np.average(v, weights=w))
    row = {'triangles': int(mask.sum()), 'samples': int(len(v)),
           'shadeMean': mean, 'shadeStd': float(np.sqrt(np.average((v-mean)**2, weights=w)))}
    for index in (3, 8):
        rgb = np.stack([np.interp(v, np.arange(256), palette[index, :, c]) for c in range(3)], 1)
        row['unlitPalette'+str(index)+'RGBMean'] = np.average(rgb, axis=0, weights=w).tolist()
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    require(not args.out.exists(), 'Output must be fresh')
    for path, expected in config['inputHashes'].items():
        require(sha(path) == expected, 'Frozen input changed: '+path)
    original_path = Path(config['originalPlt'])
    require(original_path.name == 'pmh0_pelvis001.plt', 'Only declared Human male pelvis PLT supported')
    require(str(original_path) in config['inputHashes'], 'Original PLT not frozen')
    offset = config['skinShadeOffset']
    payload, before, after, clamped = adjust_plt(original_path.read_bytes(), offset)
    archive_path = Path(config['nativeSamples'])
    labels_path = Path(config['semanticLabels'])
    palette_path = Path(config['installedPalette'])
    require(all(str(p) in config['inputHashes'] for p in [archive_path, labels_path, palette_path]),
            'Calibration inputs not frozen')
    sample = np.load(archive_path, allow_pickle=False)
    p, uv, areas = [sample['pelvis'+key] for key in ['NativePositions', 'NativeUV', 'TriangleArea']]
    labels = np.asarray(json.loads(labels_path.read_text())['labels'])
    skin_labels = labels[np.isin(labels, ['skin', 'capSkin'])]
    require(len(skin_labels) == len(p) and uv.shape == (len(p), 3, 2), 'Native face/semantic label mismatch')
    require(np.array_equal(areas, np.linalg.norm(np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]), axis=1)/2),
            'Native sample triangle area mismatch')
    bary = np.array([[1/3, 1/3, 1/3], [.6, .2, .2], [.2, .6, .2], [.2, .2, .6]])
    sample_uv = np.einsum('sc,tcd->tsd', bary, uv).reshape(-1, 2)
    old_taps, weights, yy, xx = taps(before[:, :, 0], sample_uv)
    new_taps = after[:, :, 0][yy, xx]
    before_values = np.sum(old_taps * weights, axis=1).reshape(len(p), 4)
    after_values = np.sum(new_taps * weights, axis=1).reshape(len(p), 4)
    require(np.allclose(before_values, sample['pelvisShadeSamples'], rtol=0, atol=1e-12),
            'Before native shade samples do not match frozen diagnosis')
    require(np.all(before[:, :, 1][yy, xx][weights > 0] == 0), 'Sampled skin references other PLT layer')
    palette = np.asarray(Image.open(palette_path).convert('RGB'))
    require(palette.shape[0] > 8 and palette.shape[1] == 256, 'Unexpected skin palette shape')
    groups = {'allSkinNode': np.ones(len(p), bool),
              'originalSkin': skin_labels == 'skin', 'topCapSkin': skin_labels == 'capSkin',
              'exposedOriginalLowerSkin': (skin_labels == 'skin') & (p[:, :, 2].mean(1) < -.05)}
    affected = np.any(clamped[yy, xx] & (weights > 0), axis=1).reshape(len(p), 4)
    group_results = {}
    for name, mask in groups.items():
        group_results[name] = {'before': stats(before_values, areas, mask, palette),
                              'after': stats(after_values, areas, mask, palette),
                              'samplesTouchingClampedTexel': int(affected[mask].sum()),
                              'maxBilinearDifferenceFromUnclampedOffset':
                                  float(np.abs(after_values[mask] - before_values[mask] - offset).max())}
    resource_hashes = {str(p): sha(p) for p in sorted(Path(config['nativeResources']).glob('*')) if p.is_file()}
    require(all(config['inputHashes'].get(p) == h for p, h in resource_hashes.items()),
            'Not all original native resources are frozen')
    args.out.mkdir(parents=True)
    target = args.out / 'resources' / original_path.name
    target.parent.mkdir()
    target.write_bytes(payload)
    require(target.read_bytes() == payload, 'Written PLT mismatch')
    for path, expected in config['inputHashes'].items():
        require(sha(path) == expected, 'Source modified during adjustment: '+path)
    shutil.copyfile(args.config, args.out / 'executed-config.json')
    shutil.copyfile(__file__, args.out / 'executed-adjust-pelvis-skin-plt.py')
    unique_used = np.unique((yy * before.shape[1] + xx)[weights > 0])
    report = {'schemaVersion': 1, 'operation': 'pelvis-layer0-integer-shade-offset',
              'originalPlt': str(original_path), 'originalPltSha256': sha(original_path),
              'candidate': str(target.resolve()), 'candidateSha256': sha(target),
              'skinShadeOffset': offset, 'parentHakSha256': config['parentHakSha256'],
              'parentPackageAudit': config['parentPackageAudit'],
              'inputHashes': config['inputHashes'], 'calibration': config['calibration'],
              'executedConfigSha256': sha(args.config), 'executedHelperSha256': sha(__file__),
              'widthHeight': [before.shape[1], before.shape[0]],
              'clamping': {'layer0Texels': int(np.sum(before[:, :, 1] == 0)),
                           'clampedLayer0Texels': int(clamped.sum()),
                           'changedShadeTexels': int(np.sum(before[:, :, 0] != after[:, :, 0])),
                           'nativeUsedUniqueTexels': int(len(unique_used)),
                           'nativeUsedClampedTexels': int(clamped.reshape(-1)[unique_used].sum())},
              'nativeUvGroups': group_results, 'preservedOriginalResourceHashes': resource_hashes,
              'preservation': {'headerDimensionsExact': True, 'allLayerBytesExact': True,
                               'otherLayerPixelsExact': True, 'allOriginalResourcesExact': True,
                               'geometryUvNormalsTangentsUnchanged': True,
                               'fixedBriefsMaterialUnchanged': True},
              'sampling': 'Four frozen barycentric UV samples/triangle, area weighted; raw native V flips once for image sampling. Palette rows 3/8 are unlit lookup predictions, not rendered lighting/shader results.',
              'sourceMapIntensityExact': False, 'explicitNativeMaterialDescendant': True,
              'nativeCompileRequired': False, 'clientAccepted': False}
    (args.out / 'material-correction.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'candidate': str(target), 'sha256': sha(target), 'clamping': report['clamping'],
                      'visibleSkin': group_results['exposedOriginalLowerSkin']}, indent=2))


if __name__ == '__main__':
    main()
