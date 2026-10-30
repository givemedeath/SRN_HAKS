"""Binary MDL compile and decompile through Blender and the Neverblender add-on (cleanmodels port).

Replaces the EE client `compilemodel` round trip for PhenoMorpher outputs: one headless Blender
process handles a whole folder, and the bundled cleanmodels compiler zeroes string field tails, so
binaries carry no client process memory. Lookups use only the folders a call names (the model's
own folder first): the game install, NWN_ROOT and override folders are never searched, so every
supermodel, skeleton and material a compile can read is a declared input.

The Blender executable and installed add-on stay machine-local: callers pass both explicitly and
receipts pin their hashes, never a path in a portable lock.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

WORKER = Path(__file__).with_name('neverblender_worker.py')
RECEIPT = 'native-compile.json'
EXECUTION_MODE = 'neverblender-cleanmodels'
LOOKUP_SUFFIXES = ('.mdl', '.mtr', '.txi', '.tga', '.dds', '.plt', '.2da')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def addon_files(addon):
    """{relative path: sha256} of the add-on tree the worker imports (bytecode caches excluded)."""
    addon = Path(addon).resolve()
    if not (addon/'__init__.py').is_file() or not (addon/'cleanmodels'/'__init__.py').is_file():
        raise ValueError('Neverblender add-on with its bundled cleanmodels required: ' + str(addon))
    return {p.relative_to(addon).as_posix(): digest(p.read_bytes()) for p in sorted(addon.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')}


def declared_files(blender, addon):
    """Every file a run executes or imports: the Blender executable and the add-on tree."""
    addon = Path(addon).resolve()
    return {Path(blender).resolve(), *(addon/rel for rel in addon_files(addon))}


def lookup_files(folders):
    """Files a compile may resolve from these lookup folders."""
    return {p.resolve() for folder in folders for p in Path(folder).iterdir()
            if p.is_file() and p.suffix.lower() in LOOKUP_SUFFIXES}


def toolchain(blender, addon):
    blender = Path(blender).resolve(); addon = Path(addon).resolve(); files = addon_files(addon)
    init = (addon/'__init__.py').read_text(encoding='utf-8')
    version = re.search(r"['\"]version['\"]\s*:\s*\((\d+),\s*(\d+),\s*(\d+)\)", init)
    ported = re.search(r'PORTED_FROM\s*=\s*"([^"]+)"', (addon/'cleanmodels'/'__init__.py').read_text(encoding='utf-8'))
    if not version or not ported:
        raise ValueError('Neverblender or cleanmodels version unreadable: ' + str(addon))
    identity = {'blenderSha256': digest(blender.read_bytes()), 'neverblenderFiles': files}
    return {'blender': {'path': str(blender), 'sha256': identity['blenderSha256']},
            'neverblender': {'path': str(addon), 'version': '.'.join(version.groups()),
                             'filesSha256': digest(json.dumps(files, sort_keys=True).encode())},
            'cleanmodels': ported[1], 'files': files,
            'sha256': digest(json.dumps(identity, sort_keys=True).encode())}


def run(tools, jobs, timeout=600):
    """Run jobs ({op: compile|decompile, input, output, dirs}) in one Blender process; returns its report.
    Outputs must not exist; a failed job fails the call after the batch."""
    if not jobs:
        return {'results': []}
    for job in jobs:
        if Path(job['output']).exists():
            raise FileExistsError('Fresh MDL output required: ' + str(job['output']))
    with tempfile.TemporaryDirectory(prefix='pheno-nvb-') as scratch:
        scratch = Path(scratch); request = scratch/'request.json'; report = scratch/'report.json'
        request.write_text(json.dumps({'addon': tools['neverblender']['path'], 'files': tools['files'], 'report': str(report),
                                       'jobs': [{**j, 'input': str(j['input']), 'output': str(j['output']),
                                                 'dirs': [str(d) for d in j['dirs']]} for j in jobs]}), encoding='utf-8')
        # An isolated start: factory settings, no user add-ons or startup scripts, no network, no auto-run.
        env = {k: v for k, v in os.environ.items() if k not in ('NWN_ROOT', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
        env.update(BLENDER_USER_CONFIG=str(scratch/'config'), BLENDER_USER_SCRIPTS=str(scratch/'scripts'))
        result = subprocess.run([tools['blender']['path'], '--background', '--factory-startup', '--offline-mode',
                                 '--disable-autoexec', '--python-exit-code', '3', '--python', str(WORKER), '--', str(request)],
                                capture_output=True, text=True, timeout=timeout, env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode or not report.is_file():
            raise RuntimeError('Neverblender worker failed: ' + (result.stderr or result.stdout).strip()[-2000:])
        data = json.loads(report.read_text(encoding='utf-8'))
    failed = [r for r in data['results'] if r.get('error')]
    if failed:
        raise RuntimeError('Neverblender could not process: ' + '; '.join(f"{Path(r['input']).name}: {r['error']}" for r in failed[:5]))
    return data


def audit(binary, source):
    """Decoded binary against its ASCII source: header, hierarchy, node types, bind transforms and clips."""
    from .rig_native import compare
    try:
        result = compare(binary, source)
    except ValueError as error:
        return {'passed': False, 'headerDifferences': ['undecodable: ' + str(error)], 'staticDifferences': [], 'clipFailures': []}
    return {'passed': result['passed'], 'headerDifferences': [f'{k}: {a} != {b}' for k, (a, b) in result['headerDifferences'].items()],
            'staticDifferences': result['staticRig']['differences'], 'clipFailures': result['failures'],
            'positionMetres': result['staticRig']['positionMetres'], 'rotationDegrees': result['staticRig']['rotationDegrees']}


def unresolved_supermodels(rows):
    """Models whose supermodel cleanmodels could not find. It then numbers nodes as if there were none, and the
    client applies the supermodel's animations to the wrong nodes (race-sizing r2 pmh2 stood stiff, 2026-10-27)."""
    return sorted(name for name, row in rows.items() if any('supermodel' in w and 'not found' in w for w in row['warnings']))


def compile_folder(blender, addon, converted, resource_dirs=(), timeout=600, cache=None, allow_unresolved_supermodel=False):
    """Compile converted/ascii/*.mdl into converted/resources with a native-compile.json receipt.

    Same folder layout and receipt rows as tools/phenotypes/native_compile.py, so armor-publish and
    library restoration read either. The folder's own receipt and binaries are outputs and are never
    read back. `cache` names an earlier converted folder: its binaries are copied for sources whose
    source, compiler and lookups are unchanged, so a managed launch can pin it as a read-only input.
    A supermodel missing from every lookup folder fails the compile unless explicitly allowed."""
    return compile_folders(blender, addon, [converted], resource_dirs, timeout, [cache], allow_unresolved_supermodel)[0]


def compile_folders(blender, addon, converted, resource_dirs=(), timeout=600, caches=None, allow_unresolved_supermodel=False):
    """compile_folder for several converted folders in ONE Blender process (a batch pays one start-up). Each folder
    keeps its own lookups (its ascii/, resources/ and resource_dirs), staging and receipt, identical to a
    compile_folder call on it alone. Any failure fails the call and publishes nothing into any folder."""
    tools = toolchain(blender, addon); caches = list(caches) if caches is not None else [None]*len(converted)
    if len(caches) != len(converted):
        raise ValueError('One cache entry (or None) per converted folder')
    plans = []
    try:
        for folder, cache in zip(converted, caches):
            plans.append(_plan(Path(folder).resolve(), tools, resource_dirs, cache))
        report = run(tools, [job for plan in plans for job in plan['jobs']], timeout)
        results = iter(report['results'])
        for plan in plans:
            _verify(plan, [next(results) for _ in plan['jobs']], allow_unresolved_supermodel)
        for plan in plans:  # publish only after every folder verified
            for name in plan['staged'] + [Path(job['input']).name for job in plan['jobs']]:
                os.replace(plan['staging']/name, plan['resources']/name)
    finally:
        for plan in plans:
            shutil.rmtree(plan['staging'], ignore_errors=True)
    return [_receipt(plan, tools, report) for plan in plans]


def _plan(converted, tools, resource_dirs, cache):
    cache = Path(cache).resolve() if cache else None
    if cache == converted:
        raise ValueError('The compile cache must be an earlier converted folder, not the output folder')
    sources = sorted((converted/'ascii').glob('*.mdl'))
    if not sources:
        raise ValueError('No ASCII models under ' + str(converted/'ascii'))
    resources = converted/'resources'; resources.mkdir(exist_ok=True)
    folders = [converted/'ascii', resources, *(Path(d).resolve() for d in resource_dirs)]
    names = {p.name.lower() for p in sources}
    pins = {p: digest(p.read_bytes()) for p in sorted(lookup_files(folders))
            if not (p.parent == resources and p.name.lower() in names)}
    # Files inside the folder are keyed relative to it, so a cache folder with the same contents matches.
    lookup = {(p.relative_to(converted).as_posix() if p.is_relative_to(converted) else str(p)): h for p, h in pins.items()}
    snapshot = {p.name: digest(p.read_bytes()) for p in sources}
    previous = {}
    if cache:
        if not (cache/RECEIPT).is_file():
            raise ValueError(f'Compile cache has no {RECEIPT}: {cache}')
        previous = json.loads((cache/RECEIPT).read_text(encoding='utf-8'))
    reusable = previous.get('compilerSha256') == tools['sha256'] and previous.get('lookupHashes') == lookup
    cached_rows = {r['name']: r for r in previous.get('models', [])} if reusable else {}
    plan = {'converted': converted, 'sources': sources, 'resources': resources, 'folders': folders, 'pins': pins,
            'lookup': lookup, 'snapshot': snapshot, 'previous': previous, 'rows': {}, 'jobs': [], 'staged': [],
            'staging': Path(tempfile.mkdtemp(prefix='.nvb-compile-', dir=converted))}
    for path in sources:
        cached = cached_rows.get(path.name); kept = cache/'resources'/path.name if cache else None
        if cached and cached['sourceSha256'] == snapshot[path.name] and kept.is_file():
            data = kept.read_bytes()
            if digest(data) == cached['binarySha256']:
                (plan['staging']/path.name).write_bytes(data); plan['staged'].append(path.name); plan['rows'][path.name] = cached; continue
        plan['jobs'].append({'op': 'compile', 'input': path, 'output': plan['staging']/path.name, 'dirs': folders})
    return plan


def _verify(plan, results, allow_unresolved_supermodel=False):
    failed = []
    for job, row in zip(plan['jobs'], results):
        name = Path(job['input']).name
        if row['sourceSha256'] != plan['snapshot'][name]:
            raise RuntimeError('Source changed during compilation: ' + name)
        check = audit(job['output'], job['input'])
        if not check['passed']:
            failed.append(f"{name}: {'; '.join((check['headerDifferences'] or []) + check['staticDifferences'][:3] + check['clipFailures'][:3])}")
        plan['rows'][name] = {'name': name, 'sourceSha256': row['sourceSha256'], 'binarySha256': row['outputSha256'],
                              'bytes': row['bytes'], 'seconds': row['seconds'], 'warnings': row['warnings'], 'audit': check}
    if failed:
        raise RuntimeError('Compiled binary differs from its ASCII source (cleanmodels drops model-root node '
                           'position/orientation; keep the root at the origin): ' + ' | '.join(failed[:5]))
    unresolved = unresolved_supermodels(plan['rows'])
    if unresolved and not allow_unresolved_supermodel:
        raise RuntimeError('Supermodel not found in any lookup folder, so node numbers would not match its animations '
                           '(add its folder with --resource-dir, e.g. the stock a_ba/a_fa): ' + ', '.join(unresolved[:8]))
    if any(digest(p.read_bytes()) != plan['snapshot'][p.name] for p in plan['sources']):
        raise RuntimeError('Source changed before compiler verification completed')
    if any(digest(p.read_bytes()) != pin for p, pin in plan['pins'].items()):
        raise RuntimeError('Compile lookup resource changed during compilation')


def _receipt(plan, tools, report):
    sources = plan['sources']; jobs = plan['jobs']
    receipt = {'schemaVersion': 2, 'executionMode': EXECUTION_MODE, 'compiler': {k: v for k, v in tools.items() if k != 'files'},
               'compilerSha256': tools['sha256'], 'blenderVersion': report.get('blenderVersion', plan['previous'].get('blenderVersion')),
               'lookupFolders': [str(f) for f in plan['folders']], 'lookupHashes': plan['lookup'], 'interactiveClientLaunched': False,
               'models': [plan['rows'][p.name] for p in sources], 'compiled': len(jobs), 'reused': len(sources) - len(jobs),
               'complete': True}
    (plan['converted']/RECEIPT).write_text(json.dumps(receipt, indent=1) + '\n', encoding='utf-8', newline='\n')
    return receipt


def decompile_files(blender, addon, pairs, lookup_dirs=(), timeout=600):
    """Decompile (binary input, ASCII output) pairs; each model's own folder is searched first for skeletons."""
    tools = toolchain(blender, addon)
    jobs = [{'op': 'decompile', 'input': Path(i).resolve(), 'output': Path(o).resolve(),
             'dirs': [Path(i).resolve().parent, *(Path(d).resolve() for d in lookup_dirs)]} for i, o in pairs]
    return tools, run(tools, jobs, timeout)
