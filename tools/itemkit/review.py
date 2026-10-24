"""Bounded finish-variant rendering; clay reuse never crosses a batch boundary."""
from copy import deepcopy
from pathlib import Path
import shutil
import time
from tools.headkit.common import digest, pin, verify, require, write


def geometry_review_key(config, *, _verified_scene=None):
    # Exact scene includes geometry, normals, visibility, transforms and world.
    # Family and render settings include active parts and every camera parameter.
    scene = pin(config['scene']) if _verified_scene is None else _verified_scene
    require(scene['path'] == str(Path(config['scene']).resolve()), 'Scene key path mismatch')
    return digest({'scene': scene, 'family': config['family'],
                   'render': config.get('render', {})})


def reuse_clay(config, out, previous):
    require(geometry_review_key(config) == previous['key'], 'Clay scene or cameras changed')
    frames = previous['frames']; cameras = previous['cameras']
    require(len(frames) == len(cameras) == 8, 'Incomplete clay review')
    names = [Path(row['path']).name for row in frames]
    require(len(set(names)) == 8 and all(name.startswith('clay-') and name.endswith('.png') for name in names),
            'Invalid clay review frames')
    require(all(row['mode'] == 'clay' for row in cameras), 'Invalid clay cameras')
    verify(frames)
    copied = []
    for row, name in zip(frames, names):
        target = Path(out)/name
        with target.open('xb') as dst, Path(row['path']).open('rb') as src:
            shutil.copyfileobj(src, dst)
        bound = pin(target)
        require(bound['sha256'] == row['sha256'], 'Clay copy changed')
        copied.append(bound)
    return copied, deepcopy(cameras)


def render_variants(config, textures, output, *, renderer=None):
    """Render all finishes with full lit/unlit/icon checks and one clay pass.

    The caller dispatches this through the verified launcher with all scene,
    texture and code inputs. No cache is persisted or reused on a later run.
    """
    require(textures and all(isinstance(k, str) and k.isascii() and k.replace('-', '').replace('_', '').isalnum()
                            for k in textures), 'Safe nonempty variant names required')
    if renderer is None:
        from .blender_worker import render
        renderer = render
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    scene = pin(config['scene'])
    texture_pins = {name: pin(path) for name, path in textures.items()}
    key = geometry_review_key(config, _verified_scene=scene); results = {}; clay = None; started = time.monotonic()
    for name, texture in textures.items():
        # A finish consumes only its own texture and the shared scene. Verify
        # those freshly at both boundaries, not every other finish's texture.
        inputs = [scene, texture_pins[name]]
        verify(inputs)
        cfg = deepcopy(config); cfg['scene'] = str(Path(config['scene']).resolve()); cfg['texture'] = str(Path(texture).resolve())
        require(geometry_review_key(cfg, _verified_scene=scene) == key, 'Variant geometry changed')
        folder = root/name; folder.mkdir()
        before = time.monotonic()
        result = renderer(cfg, folder, _clay_review=clay)
        verify(inputs)
        require(geometry_review_key(cfg, _verified_scene=scene) == key, 'Render changed source scene or settings')
        if clay is None:
            clay = {'key': key, 'frames': [p for p in result['frames'] if Path(p['path']).name.startswith('clay-')],
                    'cameras': [r for r in result['cameras'] if r['mode'] == 'clay']}
        result['elapsedSeconds'] = time.monotonic()-before
        write(folder/'result.json', result, fresh=True); results[name] = pin(folder/'result.json')
    report = {'variants': results, 'elapsedSeconds': time.monotonic()-started,
              'geometryRenderPasses': 1, 'reusedGeometryPasses': len(textures)-1,
              'threads': 4, 'visualApproval': False}
    write(root/'result.json', report, fresh=True)
    return report
