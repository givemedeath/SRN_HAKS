"""CPU-only, explicitly reviewed alpha transfer and paired 2K conditioning.

This does not segment opaque images, infer a camera, fill holes, discard components,
or approve references. A valid detailed alpha may replace a registered clay's bad
alpha only with pinned visual/edge evidence. CLI mutations use the shared launcher.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class Pins:
    def __init__(self):
        self.actual = {}
        self.expected = {}

    def pin(self, path):
        path = Path(path).resolve()
        key = os.path.normcase(str(path))
        if key not in self.actual:
            with path.open('rb') as source:
                self.actual[key] = hashlib.file_digest(source, 'sha256').hexdigest()
        return {'path': str(path), 'sha256': self.actual[key]}

    def check(self, row):
        path = Path(row['path'])
        require(path.is_absolute(), 'Absolute consumed paths required')
        key = os.path.normcase(str(path.resolve()))
        require(key not in self.expected or self.expected[key] == row['sha256'], 'Conflicting expected pins')
        self.expected[key] = row['sha256']
        require(self.pin(path)['sha256'] == row['sha256'], 'Stale consumed input: ' + str(path))


def save(path, data):
    with Path(path).open('x', encoding='utf-8', newline='\n') as output:
        json.dump(data, output, indent=2, allow_nan=False)
        output.write('\n')


def registration(evidence, detail, clay, size, *, transfer=True):
    require(evidence.get('detailSha256') == detail['sha256'] and
            evidence.get('claySha256') == clay['sha256'], 'Stale registration evidence')
    require(evidence.get('actualImagesViewed') is True and
            evidence.get('maskTransferVisuallyReviewed' if transfer else 'pairMasksVisuallyReviewed') is True and
            bool(evidence.get('notes', '').strip()), 'Explicit visual mask-transfer review required')
    points = evidence.get('landmarks', [])
    require(len(points) >= 4 and len({p['name'] for p in points}) == len(points), 'Four distinct paired landmarks required')
    require(all(isinstance(p['name'], str) and p['name'].strip() for p in points), 'Named landmarks required')
    distances = []
    width, height = size
    for point in points:
        for role in ('detail', 'clay'):
            xy = point[role]
            require(len(xy) == 2 and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in xy),
                    'Normalized finite landmarks required')
        distance = math.dist(point['detail'], point['clay'])
        require(distance <= .02, 'Paired landmarks exceed 2% of the frame')
        pixels = math.hypot((point['detail'][0] - point['clay'][0]) * width,
                            (point['detail'][1] - point['clay'][1]) * height)
        require(not transfer or pixels <= 3, 'Mask transfer needs registration within three source pixels')
        distances.append(distance)
    require(all(len({tuple(p[role]) for p in points}) >= 4 for role in ('detail', 'clay')),
            'Four distinct landmark positions required')
    edges = evidence.get('edgeMeasurements', [])
    require(len(edges) >= 4 and all(type(e.get('offsetPixels')) in (float, int) and
            math.isfinite(e['offsetPixels']) and (not transfer or abs(e['offsetPixels']) <= 3) for e in edges),
            'Four measured silhouette edges within three pixels required')
    require(evidence.get('intentionalOpeningsReviewed') is True and
            evidence.get('thinMembersReviewed') is True, 'Review openings and thin members')
    return {'landmarks': points, 'maximumFrameDistance': max(distances), 'edgeMeasurements': edges,
            'maximumEdgeOffsetPixels': max(abs(e['offsetPixels']) for e in edges)}


def topology(mask):
    import numpy as np
    from scipy import ndimage
    foreground = np.asarray(mask) >= 128
    components = int(ndimage.label(foreground)[1])
    # Counting holes is diagnostic only; the mask is never filled or simplified.
    background, count = ndimage.label(~foreground)
    border = set(np.unique(np.concatenate([background[0], background[-1], background[:, 0], background[:, -1]])))
    return {'components': components, 'holes': sum(i not in border for i in range(1, count + 1))}


def prepare(spec_path, output):
    import numpy as np
    from PIL import Image
    started = time.perf_counter()
    spec_path, output = Path(spec_path).resolve(), Path(output).resolve()
    require(not output.exists(), 'Use a fresh output directory')
    spec = read(spec_path)
    route = spec.get('route')
    require(route in ('replace-invalid-clay-alpha-from-registered-detail', 'preserve-reviewed-pair-alpha'),
            'Explicit mask-transfer or independently reviewed alpha route required')
    transfer = route == 'replace-invalid-clay-alpha-from-registered-detail'
    pins = Pins()
    for row in [spec['detail'], spec['clay'], spec['registrationEvidence'], *spec.get('sourceDependencies', [])]:
        pins.check(row)
    size = spec.get('canvasSize', 2048)
    require(type(size) is int and size == 2048, 'This preparation emits a 2048 square canvas')
    padding = spec.get('paddingPixels', 102)
    require(type(padding) is int and 64 <= padding <= 256, 'Review 64..256 pixels of canvas padding')
    floor = spec.get('sourceAlphaFloor', 16)
    require(type(floor) is int and 0 <= floor <= 16, 'Alpha floor must not erase opaque thin structures')
    with Image.open(spec['detail']['path']) as source:
        require('A' in source.getbands(), 'Detailed reference needs existing valid alpha')
        detail = np.array(source.convert('RGBA'))
    with Image.open(spec['clay']['path']) as source:
        require(transfer or 'A' in source.getbands(), 'Clay reference needs existing valid alpha')
        clay = np.array(source.convert('RGBA'))
    require(detail.shape == clay.shape, 'Source canvases must match before alpha transfer')
    height, width = detail.shape[:2]
    evidence = read(spec['registrationEvidence']['path'])
    measured = registration(evidence, spec['detail'], spec['clay'], (width, height), transfer=transfer)
    alphas = {'detail': detail[:, :, 3].copy(), 'clay': detail[:, :, 3].copy() if transfer else clay[:, :, 3].copy()}
    for role, alpha in alphas.items():
        alpha[alpha < floor] = 0
        solid = alpha >= 128
        require(solid.any() and float(solid.mean()) < .95, 'Nonempty isolated source alpha required: ' + role)
        require(not (solid[0].any() or solid[-1].any() or solid[:, 0].any() or solid[:, -1].any()),
                'Source alpha is clipped: ' + role)
        ys, xs = np.nonzero(alpha)
        require(xs.min() > 0 and ys.min() > 0 and xs.max() < width - 1 and ys.max() < height - 1,
                'Nonzero alpha reaches the frame; review it before preparation: ' + role)
    ys, xs = np.nonzero(np.maximum(alphas['detail'], alphas['clay']))
    bounds = [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]
    left, top, right, bottom = bounds
    scale = min((size - 2 * padding) / (right - left), (size - 2 * padding) / (bottom - top))
    resized = [round((right - left) * scale), round((bottom - top) * scale)]
    offset = [(size - resized[0]) // 2, (size - resized[1]) // 2]
    output_landmarks = []
    for point in measured['landmarks']:
        row = {'name': point['name']}
        for role in ('detail', 'clay'):
            x, y = point[role]
            row[role] = [((x * width - left) * resized[0] / (right - left) + offset[0]) / size,
                         ((y * height - top) * resized[1] / (bottom - top) + offset[1]) / size]
        require(all(0 <= value <= 1 for role in ('detail', 'clay') for value in row[role]) and
                math.dist(row['detail'], row['clay']) <= .02, 'Conditioned landmarks exceed canvas/alignment bounds')
        output_landmarks.append(row)
    ox, oy = offset
    source_topology = {role: topology(alpha) for role, alpha in alphas.items()}
    output_topology = {}
    output.mkdir(parents=True, exist_ok=False)
    artifacts = {}
    for role, source in [('detail', detail), ('clay', clay)]:
        alpha = alphas[role]
        crop_alpha = alpha[top:bottom, left:right].astype(np.float32) / 255
        resized_alpha = np.clip(np.array(Image.fromarray(crop_alpha).resize(resized, Image.Resampling.LANCZOS)), 0, 1)
        mask = np.zeros((size, size), dtype=np.uint8)
        mask[oy:oy + resized[1], ox:ox + resized[0]] = np.rint(resized_alpha * 255).astype(np.uint8)
        output_topology[role] = topology(mask)
        require(output_topology[role] == source_topology[role], 'Resampling changed source-mask components or openings: ' + role)
        native = source.copy()
        native[:, :, 3] = alpha
        Image.fromarray(native).save(output / (role + '-foreground-native.png'))
        black = np.zeros((size, size, 3), dtype=np.uint8)
        premultiplied = source[top:bottom, left:right, :3].astype(np.float32) * crop_alpha[:, :, None]
        color = np.stack([np.clip(np.array(Image.fromarray(premultiplied[:, :, c]).resize(resized, Image.Resampling.LANCZOS)), 0, 255)
                          for c in range(3)], axis=2)
        # Negative Lanczos lobes can overshoot color relative to alpha even when
        # each channel is independently in range. A valid premultiplied channel
        # cannot exceed alpha*255; clamp that color footprint without changing
        # the mask, its antialiasing, or any native source RGB bytes.
        color = np.minimum(color, mask[oy:oy + resized[1], ox:ox + resized[0], None])
        # Clear zero-mask resampling footprints, without eroding any mask pixels.
        color[mask[oy:oy + resized[1], ox:ox + resized[0]] == 0] = 0
        black[oy:oy + resized[1], ox:ox + resized[0]] = np.rint(color).astype(np.uint8)
        Image.fromarray(black).save(output / (role + '-conditioning-2048.png'))
        Image.fromarray(mask).save(output / (role + '-mask-2048.png'))
        rgba = np.zeros((size, size, 4), dtype=np.uint8)
        ratio = mask.astype(np.float32) / 255
        nonzero = ratio > 0
        rgba[nonzero, :3] = np.clip(np.rint(black[nonzero] / ratio[nonzero, None]), 0, 255).astype(np.uint8)
        rgba[:, :, 3] = mask
        Image.fromarray(rgba).save(output / (role + '-rgba-2048.png'))
        preview = Image.new('RGB', (size, size), (0, 130, 140))
        preview.paste(Image.fromarray(rgba), (0, 0), Image.fromarray(mask))
        preview.save(output / (role + '-teal-review.png'))
        artifacts[role] = {kind: pins.pin(output / name) for kind, name in [
            ('foregroundNative', role + '-foreground-native.png'), ('conditioning', role + '-conditioning-2048.png'),
            ('mask', role + '-mask-2048.png'), ('rgba', role + '-rgba-2048.png'), ('preview', role + '-teal-review.png')]}
    with Image.open(artifacts['detail']['preview']['path']) as a, Image.open(artifacts['clay']['preview']['path']) as b:
        Image.blend(a, b, .5).save(output / 'paired-overlay-review.png')
    # A fresh post-execution pass catches changes even when timestamps are restored.
    after = Pins()
    for row in [spec['detail'], spec['clay'], spec['registrationEvidence'], *spec.get('sourceDependencies', [])]:
        after.check(row)
    result = {'kind': 'cpu-paired-reference-conditioning-candidate', 'spec': pins.pin(spec_path),
              'helper': pins.pin(__file__), 'rawSources': {'detail': spec['detail'], 'clay': spec['clay']},
              'route': route, 'sourceAlphaFloor': floor, 'sourceNativeDimensions': [width, height],
              'provenanceRawSources': spec.get('provenanceRawSources', {}),
              'outputDimensions': [size, size], 'native2K': False, 'resampled2K': True,
              'transform': {'commonCrop': bounds, 'uniformScaleBeforePixelRounding': scale,
                            'resizedDimensions': resized, 'commonOffset': offset, 'independentCropping': False},
              'registration': measured, 'sourceMaskTopology': source_topology, 'outputMaskTopology': output_topology,
              'conditionedPairedLandmarks': output_landmarks,
              # This step discards and fills nothing; keying before it (an oblique pair) may have, and says so here.
              'rawRgbPreservedInNativeForegroundCopies': True, 'componentsDiscarded': 0, 'holesFilled': 0,
              'sourceKeying': spec.get('sourceKeying'),
              'premultipliedColorBoundedByResampledAlpha': True,
              'artifacts': artifacts, 'overlay': pins.pin(output / 'paired-overlay-review.png'),
              'inputsFreshBeforeAndAfter': True, 'visualParentReviewRequired': True,
              'conditionedReferenceAccepted': False, 'readyForGeometry': False,
              'elapsedSeconds': time.perf_counter() - started, 'gpuOrInferenceUsed': False}
    save(output / 'conditioning-candidate.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(os.environ.get('SRN_SHARED_TOOLCHAIN') and os.environ.get('SRN_VERIFIED_INPUTS'),
            'Run image preparation through the verified shared-tool launcher')
    snapshot = read(os.environ['SRN_VERIFIED_INPUTS'])
    require(snapshot.get('kind') == 'verified-shared-input-snapshot', 'Verified launcher snapshot required')
    frozen = {os.path.normcase(str(Path(path).resolve())): digest for path, digest in snapshot['files'].items()}
    spec = read(args.spec)
    consumed = [args.spec.resolve(), Path(__file__).resolve()] + [Path(p['path']).resolve() for p in
                [spec['detail'], spec['clay'], spec['registrationEvidence'], *spec.get('sourceDependencies', [])]]
    declared = Pins()
    for path in consumed:
        key = os.path.normcase(str(path))
        require(key in frozen, 'Undeclared conditioning input: ' + str(path))
        declared.check({'path': str(path), 'sha256': frozen[key]})
    print(json.dumps(prepare(args.spec, args.output)))


if __name__ == '__main__':
    main()
