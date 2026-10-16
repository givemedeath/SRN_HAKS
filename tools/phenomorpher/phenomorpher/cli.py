"""Managed PhenoMorpher CLI. Inspect/help are harmless; data runs use run.py."""
import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from . import __version__
from . import api


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


_PINS = None


def snapshot():
    global _PINS
    if _PINS is None:
        path = os.environ.get('SRN_VERIFIED_INPUTS')
        if not path:
            raise ValueError('Use run.py with a passed shared-tool migration')
        _PINS = read(path)['files']
    return _PINS


def declared(path):
    receipt_path = os.environ.get('SRN_VERIFIED_INPUTS')
    if not receipt_path:
        raise ValueError('Use the repository run.py entry point with a passed shared-tool migration')
    pins = snapshot()
    resolved = str(Path(path).resolve())
    if resolved not in pins:
        raise ValueError('Consumed file is undeclared or changed: ' + resolved)


def fresh(path):
    result = Path(path)
    result.mkdir(parents=True, exist_ok=False)
    return result


def assembly(root, path):
    declared(path)
    data = read(path)
    if data.get('kind') != 'PhenoMorpher-assembly' or data.get('schemaVersion') != 1:
        raise ValueError('Versioned assembly required')
    rig = api.bound(root, data['rig'], snapshot())
    parts = {n: api.bound(root, row, snapshot()) for n, row in data['parts'].items()}
    for file in [rig, *parts.values()]:
        declared(file)
    return data, rig, parts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='PhenoMorpher ' + __version__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    for command in ('catalog', 'verify-assets'):
        p = sub.add_parser(command); p.add_argument('--manifest', type=Path, required=True)
        p.add_argument('--root', type=Path, required=True)
    p = sub.add_parser('measure'); p.add_argument('--assembly', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('native-info'); p.add_argument('--input', type=Path, required=True)
    p = sub.add_parser('candidate'); p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('replay'); p.add_argument('--release', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('convert-clothing')
    for name in ('release', 'profile', 'source-binding', 'input', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--class', dest='garment_class', choices=['modular-close','modular-loose','rigid-island'], required=True)
    p = sub.add_parser('anim-library'); actions = p.add_subparsers(dest='action', required=True)
    s = actions.add_parser('extract-stock'); s.add_argument('--resman-cat', type=Path, required=True)
    s.add_argument('--game-root', type=Path, required=True); s.add_argument('--seed', action='append', required=True)
    s.add_argument('--output', type=Path, required=True)
    s = actions.add_parser('inventory')
    for name in ('root', 'manifest', 'stock', 'output'):
        s.add_argument('--' + name, type=Path, required=True)
    s = actions.add_parser('build')
    for name in ('root', 'manifest', 'stock', 'output'):
        s.add_argument('--' + name, type=Path, required=True)
    for name in ('fit', 'large', 'name'):
        s.add_argument('--' + name, required=True)
    s.add_argument('--authorized-fit-clip', action='append', default=[])
    s = actions.add_parser('restore')
    for name in ('root', 'plan', 'compiled', 'output'):
        s.add_argument('--' + name, type=Path, required=True)
    s = actions.add_parser('repoint'); s.add_argument('--input', type=Path, required=True)
    s.add_argument('--parent', required=True); s.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('compare-motion')
    for name in ('root', 'manifest', 'stock', 'repointed', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--library', type=Path, help='Library the root names; omit when it names a stock model')
    p.add_argument('--target', required=True); p.add_argument('--authorized-fit-clip', action='append', default=[])
    p = sub.add_parser('downsample-textures')
    for name in ('root', 'manifest', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--max-size', type=int, default=1024)
    p = sub.add_parser('adopt-runtime')
    for name in ('root', 'plan', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p = sub.add_parser('audit-native')
    for name in ('published', 'source', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p = sub.add_parser('sweep')
    for name in ('root', 'manifest', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--target', action='append', required=True, help='Model prefix; repeat per body')
    p.add_argument('--stock', type=Path, help='Extracted stock manifest; required for --motion')
    p.add_argument('--motion', action='store_true'); p.add_argument('--motion-only', action='store_true')
    p.add_argument('--clip', action='append', help='Restrict the motion sweep to these clips')
    p.add_argument('--label')
    p = sub.add_parser('armor-extract')
    for name in ('resman-extract', 'decompiler', 'game-root', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--slot', action='append', help='Body slot such as pfd0; repeat (default: all)')
    p = sub.add_parser('armor-profiles')
    for name in ('root', 'manifest', 'stock', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--slot', action='append', help='Body slot such as pfd0; repeat (default: all)')
    p = sub.add_parser('armor-convert')
    for name in ('stock', 'profiles', 'armory', 'styles', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--slot', action='append', help='Body slot such as pfd0; repeat (default: all)')
    p = sub.add_parser('retarget-v2')
    p.add_argument('--fit-converted', type=Path, required=True); p.add_argument('--large-converted', type=Path)
    p.add_argument('--baseline', type=Path, required=True, help='Extracted stock baseline (baseline.json and ascii/)')
    p = sub.add_parser('verify-runtime')
    for name in ('root', 'manifest', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--stock', type=Path, help='Extracted stock manifest for the deep installed-chain check')
    p.add_argument('--max-texture', type=int, default=1024)
    a = parser.parse_args(argv)
    if a.command == 'doctor':
        declared(__file__)
        from .engine.measurement_workflow import smoke
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            smoke()
        result = json.loads(output.getvalue())
        result['loadedPackageSources'] = {
            name: {'path': str(Path(module.__file__).resolve()), 'sha256': api.digest(module.__file__)}
            for name, module in sorted(sys.modules.items())
            if (name == 'phenomorpher' or name.startswith('phenomorpher.'))
            and getattr(module, '__file__', None)
        }
        print(json.dumps(result)); return
    if a.command in ('catalog', 'verify-assets'):
        declared(a.manifest); m = read(a.manifest)
        if a.command == 'catalog':
            print(json.dumps({'version': m['version'], 'targets': m['targets']})); return
        for row in m['resources']: declared(a.root / row['path'])
        print(json.dumps(api.verify_assets(a.root, a.manifest, snapshot()))); return
    if a.command == 'native-info':
        declared(a.input); skeleton, attributes, source_pin = api.read_attributes(a.input)
        print(json.dumps({'nodes': len(skeleton), 'meshes': [{'node': n, 'vertices': len(row['position']),
            'triangles': len(row['faces']), 'attributes': [k for k in ('normal','uv','tangent','sign','color') if k in row]}
            for n, row in attributes.items()], 'sourcePin': source_pin})); return
    if a.command == 'measure':
        data, rig, parts = assembly(a.root, a.assembly)
        meshes, joints = api.assemble(rig, parts); out = fresh(a.output)
        report = api.measure(meshes, joints)
        report.update(space='bind/rest geometry', includesHead='head' in parts,
                      runtimeStatureVerified=False, assetApprovalCreated=False)
        views = {}
        for view in ('front','left','back','right'):
            mask, _, dimensions = api.rasterize(meshes, view)
            Image.fromarray((mask * 255).astype(np.uint8)).save(out / (view + '.png'))
            views[view] = dimensions
        api.save_recipe(out/'measurements.json', report); api.save_recipe(out/'views.json', views)
        print(json.dumps(report)); return
    if a.command == 'candidate':
        declared(a.bundle); data = api.load_recipe(a.bundle)
        for path, expected in data['motion'].get('inputPins', {}).items():
            declared(path)
            if snapshot()[str(Path(path).resolve())] != expected:
                raise ValueError('Candidate motion source pin changed: ' + path)
        for mesh in data['bindMeshes']:
            if 'sourceAttributes' not in mesh:
                raise ValueError('Original sourceAttributes required for candidate scene export')
            if mesh.get('sourceAttributePin'):
                pin=mesh['sourceAttributePin'];declared(pin['path'])
                if snapshot()[str(Path(pin['path']).resolve())] != pin['sha256']:
                    raise ValueError('Candidate source attribute pin changed')
        first, second = api.fit_candidate(data['bindMeshes'], data['bindFrames'], data['motion'],
                                         data['reference'], data.get('policy'))
        out = fresh(a.output)
        api.save_recipe(out/'first-pass.json', first); api.save_recipe(out/'morphed-proposal.json', second)
        api.save_recipe(out/'connector-report.json', api.audit_connectors(
            first['sourceStandingMeshes'], second['standingMeshes'],
            first['sourceStandingFrames'], second['standingFrames'], second['partScales']))
        api.display_scene(second, {n: row['parent'] for n, row in data['motion']['skeleton'].items()}, out/'proposal-clay.glb')
        print(json.dumps(second['receipt'], default=api.encode)); return
    if a.command == 'replay':
        manifest=a.release/'recipes/manifest.json';declared(manifest)
        for row in read(manifest)['targets']:
            recipe=api.bound(a.release,row['recipe'],snapshot());declared(recipe)
            data=read(recipe)
            for name in ('highDetail','metadata','correspondence','reducedGeometry'):
                declared(api.bound(a.release,data[name],snapshot()))
        from .engine.replay_bodies import run
        print(json.dumps(run(a.release, a.output))); return
    if a.command in ('anim-library', 'compare-motion'):
        from .engine import anim_library
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        action = a.command if a.command == 'compare-motion' else a.action
        if action == 'extract-stock':
            result = anim_library.extract_stock(a.resman_cat, a.game_root, a.seed, a.output)
            print(json.dumps({'models': len(result['models']), 'seeds': result['seeds']})); return
        if action == 'build':
            result = anim_library.build(a.root, a.manifest, a.stock, a.fit, a.large, a.name, a.output, a.authorized_fit_clip)
            print(json.dumps({k: result[k] for k in ('library', 'retained', 'inherited', 'fitLargeDifferences')})); return
        if action == 'restore':
            result = anim_library.restore(a.root, a.plan, a.compiled, a.output)
            print(json.dumps({k: v for k, v in result.items() if k != 'eventOrderRestored'})); return
        if a.output.exists(): raise ValueError('Fresh output required')
        a.output.parent.mkdir(parents=True, exist_ok=True)
        if action == 'repoint':
            data = anim_library.repoint(a.input.read_bytes(), a.parent); a.output.write_bytes(data)
            print(json.dumps({'output': str(a.output), 'sha256': anim_library.digest(data)})); return
        if action == 'compare-motion':
            from .engine.motion_compare import compare
            result = compare(a.root, a.manifest, a.stock, a.target, a.library, a.repointed, a.authorized_fit_clip)
            summary = {k: result[k] for k in ('target', 'newChain', 'counts', 'failures', 'passed')}
        else:
            result = anim_library.inventory(a.root, a.manifest, a.stock); summary = result['summary']
        a.output.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(summary))
        if not result.get('passed', True): raise SystemExit(1)
        return
    if a.command == 'downsample-textures':
        from .engine.texture_downsample import downsample
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        print(json.dumps(downsample(a.root, a.manifest, a.output, a.max_size)['summary'])); return
    if a.command == 'adopt-runtime':
        from .engine.runtime_release import adopt
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        print(json.dumps(adopt(a.root, a.plan, a.output)['summary'])); return
    if a.command == 'audit-native':
        from .engine.rig_native import compare
        for path in (a.published, a.source): declared(path)
        if a.output.exists(): raise ValueError('Fresh output required')
        result = compare(a.published, a.source)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, indent=1) + chr(10), encoding='utf-8', newline=chr(10))
        print(json.dumps({k: result[k] for k in ('failures', 'headerDifferences', 'passed')}))
        if not result['passed']: raise SystemExit(1)
        return
    if a.command == 'sweep':
        from .engine.body_sweep import sweep
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        print(json.dumps(sweep(a.root, a.manifest, a.output, a.target, a.stock, a.motion or a.motion_only, a.motion_only, a.clip, a.label)))
        return
    if a.command == 'armor-extract':
        from .engine.stock_armor import SOURCES, extract
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        result = extract(a.resman_extract, a.decompiler, a.game_root, a.output, a.slot or SOURCES)
        print(json.dumps(result['counts'])); return
    if a.command == 'armor-profiles':
        from .engine.stock_armor import TARGETS, fit_profiles
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        result = fit_profiles(a.root, a.manifest, a.stock, a.output, a.slot or TARGETS)
        print(json.dumps({'slots': len(result['slots']), 'flagged': result['flagged']})); return
    if a.command == 'armor-convert':
        from .engine.stock_armor import TARGETS, convert, style_set
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        result = convert(a.stock, a.profiles, a.armory, a.output, a.slot or TARGETS, style_set(a.styles))
        print(json.dumps({**result['counts'], 'worstWorldTransformError': result['worstWorldTransformError']})); return
    if a.command == 'retarget-v2':
        from .engine.retarget_v2 import retarget
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        receipt = retarget(a.fit_converted, a.baseline, a.large_converted)
        print(json.dumps({k: receipt[k] for k in ('motionSource', 'topCarrier', 'fitLargeShareMotion')}))
        return
    if a.command == 'verify-runtime':
        from .engine.runtime_rules import check
        from .inputs import consumed
        snapshot()  # Managed launches only, before any declared file is parsed.
        for path in consumed(argv if argv is not None else sys.argv[1:]): declared(path)
        if a.output.exists(): raise ValueError('Fresh output required')
        result = check(a.root, a.manifest, a.stock, a.max_texture)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({k: result[k] for k in ('contractVersion', 'mode', 'violationCounts', 'passed')}))
        if not result['passed']: raise SystemExit(1)
        return
    if a.command == 'convert-clothing':
        for path in (a.profile,a.source_binding,a.input):declared(path)
        data=read(a.profile)
        for name in ('sourceBody','targetBody'):
            body=api.bound(a.release,data[name],snapshot());declared(body)
            for row in read(body)['files'].values():declared(api.bound(a.release,row,snapshot()))
        from .engine.convert_model import main as convert
        old = sys.argv
        try:
            sys.argv = ['convert'] + sum(([f'--{name}', str(getattr(a, name.replace('-', '_')))]
                for name in ('release','profile','source-binding','input','output')), []) + ['--class',a.garment_class]
            convert()
        finally:
            sys.argv = old


if __name__ == '__main__':
    main()
