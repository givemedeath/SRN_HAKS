"""Tile models ship compiled; their ASCII sources stay in the repository (user, 2026-11-20).

A tile pack's model `<pack>/<name>.mdl` that has a source `sources/<pack>/<name>.mdl` is the binary NeverBlender compiled
from that source. The packs are what the game loads, and a compiled model loads several times faster than ASCII
(dgt04 review areas: 3.8-6.8 s packed ASCII, 1.1-2.0 s compiled, 2026-11-20). The tile tools read and write the
sources (`source`); `compile_models` makes the binaries, and `sources/compiled.json` pins each pair by hash, so a
source changed without a compile, or a binary changed by hand, is caught (`check`, run by the tests).

Each binary is checked against its source before any is written (`audit`):
- the decoded hierarchy, node types and bind transforms (rig_native, with tile tolerances: 10 micrometres, 0.001 deg);
- every animation the decoder cannot compare (emitter controllers, node names in another case), and every model it
  cannot decode (a node name used twice), by decompiling the binary again and comparing nodes and keys;
- animation nodes the compiler warns it dropped (a duplicate name, not joined to the root) are the only difference
  allowed, recorded in the manifest. The client's own compiler, which cleanmodels ports, drops them too.
One failure writes nothing."""
import datetime
import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path

from . import require

SOURCES = 'sources'
MANIFEST = 'sources/compiled.json'
KIND = 'tilekit-compiled-models'
TOLERANCES = {'positionMetres': 1e-5, 'rotationDegrees': 1e-3}
VALUE_TOLERANCE = 1e-4  # other keyed values (colours, rates, sizes) after the float32 a binary stores
DROPPED = re.compile(r'animation "([^"]+)": \d+ animation node\(s\) are not connected to the root and were left out of the binary: (.+)$')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def source(repo, path):
    """The ASCII source of a pack file `path` (`sources/<pack>/<name>`) when the repository keeps one, else `path`."""
    path = Path(path); kept = Path(repo) / SOURCES / path.parent.name / path.name
    return kept if path.suffix.lower() == '.mdl' and kept.is_file() else path


def source_target(repo, pack_path):
    """Where a tile model written for the pack file `pack_path` goes: its source, in a tile pack whose models ship
    compiled (one with a `sources/<pack>/` folder, `adopt`); else the pack file itself."""
    pack_path = Path(pack_path); kept = Path(repo) / SOURCES / pack_path.parent.name
    return kept / pack_path.name if pack_path.suffix.lower() == '.mdl' and tile_pack(pack_path.parent.name) and kept.is_dir() else pack_path


def tile_pack(pack):
    """Whether a pack's tile models ship compiled from sources: the tile packs, `srn_t_*`."""
    return str(pack).lower().startswith('srn_t_')


def manifest(repo):
    path = Path(repo) / MANIFEST
    if not path.is_file():
        return {'schemaVersion': 1, 'kind': KIND, 'models': {}}
    told = json.loads(path.read_text(encoding='utf-8-sig')); require(told.get('kind') == KIND, f'{MANIFEST} is not a {KIND} record')
    return told


def sources(repo):
    """{'<pack>/<name>.mdl': source path} of every kept source."""
    root = Path(repo) / SOURCES
    return {f'{path.parent.name}/{path.name}': path for path in sorted(root.glob('*/*.mdl'))} if root.is_dir() else {}


def check(repo):
    """What does not hold: a source without its binary, a source or binary that is not the pair the manifest pins, a
    manifest row without a source. [] when all hold."""
    repo = Path(repo); rows = manifest(repo)['models']; kept = sources(repo); problems = []
    for key, path in kept.items():
        pack, name = key.split('/'); binary = repo / pack / name; row = rows.get(key)
        if not tile_pack(pack):
            problems.append(f'{key}: sources are kept for tile packs (srn_t_*) only')
        elif row is None:
            problems.append(f'{key}: not compiled (no row in {MANIFEST})')
        elif _sha(path.read_bytes()) != row['source']:
            problems.append(f'{key}: the source changed since it was compiled')
        elif not binary.is_file():
            problems.append(f'{key}: the pack has no {name}')
        elif _sha(binary.read_bytes()) != row['binary']:
            problems.append(f'{key}: the pack copy is not the binary compiled from the source')
    problems += [f'{key}: {MANIFEST} has a row, and there is no source' for key in sorted(set(rows) - set(kept))]
    return problems


def stale(repo):
    """The sources whose pack binary is missing or not the one the manifest pins to the source as it is now."""
    repo = Path(repo); rows = manifest(repo)['models']; out = []
    for key, path in sources(repo).items():
        pack, name = key.split('/'); row = rows.get(key); binary = repo / pack / name
        if not (row and binary.is_file() and _sha(path.read_bytes()) == row['source'] and _sha(binary.read_bytes()) == row['binary']):
            out.append(key)
    return out


# --- the round trip: a binary decompiled again, against its source ---------------------------------------------------

def _numbers(words):
    try:
        return [float(word) for word in words]
    except ValueError:
        return None


def read_ascii(text):
    """{'nodes': [(type, name, parent)], 'bind': {name: {position, orientation}}, 'animations': {name: {'length',
    'transtime', 'events', 'nodes': {node: {controller: rows}}}}} of an ASCII model, names in lower case. A node name
    used twice in one block gets '#2', '#3'."""
    nodes, bind, animations, block, node, key, rows = [], {}, {}, None, None, None, None
    names = {}
    for raw in text.replace('\r', '').split('\n'):
        words = raw.split('#', 1)[0].split()
        if not words:
            continue
        word = words[0].lower()
        if key is not None:  # the rows of a keyed controller: numbers until one is not
            values = _numbers(words)
            if values is not None and (rows is None or len(rows) < key[1]):
                (rows if rows is not None else []).append(values); continue
            node[key[0]] = rows; key, rows = None, None
            if word == 'endlist':
                continue
        if word == 'newanim':
            block = animations[words[1].lower()] = {'length': None, 'transtime': None, 'events': [], 'nodes': {}}; names = {}
        elif word == 'doneanim':
            block = None
        elif word == 'node':
            name = words[2].lower(); count = names[name] = names.get(name, 0) + 1; name = name if count == 1 else f'{name}#{count}'
            if block is None:
                nodes.append([words[1].lower(), name, None]); node = bind[name] = {'position': [0.0, 0.0, 0.0], 'orientation': [0.0, 0.0, 0.0, 0.0]}
            else:
                node = block['nodes'].setdefault(name, {})
        elif word == 'endnode':
            node = None
        elif word == 'parent' and block is None and nodes and node is not None:
            nodes[-1][2] = words[1].lower()
        elif word in ('position', 'orientation') and block is None and node is not None and _numbers(words[1:]):
            node[word] = _numbers(words[1:])
        elif block is not None and node is None and word in ('length', 'transtime'):
            block[word] = float(words[1])
        elif block is not None and node is None and word == 'event':
            block['events'].append((round(float(words[1]), 4), words[2].lower()))
        elif block is not None and node is not None and word.endswith('key'):
            count = int(words[1]) if len(words) > 1 and words[1].isdigit() else 1 << 30
            key, rows = (word, count), []
        elif block is not None and node is not None and word != 'parent' and len(words) > 1 and _numbers(words[1:]) is not None:
            node[word + 'key'] = [[0.0] + _numbers(words[1:])]  # a plain value in an animation is its one key: the compiler keys it
        elif word == 'beginmodelgeom':
            names = {}
    if key is not None:
        node[key[0]] = rows
    return {'nodes': [tuple(entry) for entry in nodes], 'bind': bind, 'animations': animations}


def _quaternion(row):
    x, y, z, angle = row; norm = math.sqrt(x * x + y * y + z * z)
    if norm < 1e-12 or abs(angle) < 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    s = math.sin(angle / 2) / norm
    return (x * s, y * s, z * s, math.cos(angle / 2))


def _controller(name, a, b):
    """The difference of one keyed controller, or None when it holds."""
    if len(a) != len(b):
        return f'{len(a)} keys != {len(b)}'
    for x, y in zip(a, b):
        if len(x) != len(y) or abs(x[0] - y[0]) > 1e-4:
            return f'key at {x[0]:g} differs in time or width'
        if name == 'orientationkey' and len(x) == 5:
            p, q = _quaternion(x[1:]), _quaternion(y[1:]); dot = min(1.0, abs(sum(i * j for i, j in zip(p, q))))
            if math.degrees(2 * math.acos(dot)) > TOLERANCES['rotationDegrees']:
                return f'key at {x[0]:g}: rotation differs'
        elif name == 'positionkey':
            if math.dist(x[1:], y[1:]) > TOLERANCES['positionMetres']:
                return f'key at {x[0]:g}: position differs'
        elif any(abs(i - j) > VALUE_TOLERANCE * max(1.0, abs(i)) for i, j in zip(x[1:], y[1:])):
            return f'key at {x[0]:g}: values differ'
    return None


def round_trip(source_text, back_text, dropped=()):
    """The differences of a decompiled binary from its source: geometry nodes (type, name, parent, bind position and
    orientation), and each animation's length, events, keyed nodes and keys. `dropped`: {(animation, node)} the
    compiler warned it left out."""
    a, b = read_ascii(source_text), read_ascii(back_text); out = []
    if sorted(a['nodes']) != sorted(b['nodes']):
        only = sorted(set(a['nodes']) ^ set(b['nodes']))[:3]
        out.append('geometry nodes differ: ' + ', '.join(f'{name} ({kind}, under {parent})' for kind, name, parent in only))
    for name in sorted(set(a['bind']) & set(b['bind'])):  # the bind transforms, as the rig audit checks a model it can decode
        told = _controller('positionkey', [[0.0] + a['bind'][name]['position'][:3]], [[0.0] + b['bind'][name]['position'][:3]])             or _controller('orientationkey', [[0.0] + a['bind'][name]['orientation'][:4]], [[0.0] + b['bind'][name]['orientation'][:4]])
        if told:
            out.append(f'{name}: bind ' + told.split(': ', 1)[-1])
    for name in sorted(set(a['animations']) | set(b['animations'])):
        x, y = a['animations'].get(name), b['animations'].get(name)
        if x is None or y is None:
            out.append(f'{name}: only in the {"source" if y is None else "binary"}'); continue
        for field in ('length', 'transtime'):
            if x[field] is not None and y[field] is not None and abs(x[field] - y[field]) > 1e-4:
                out.append(f'{name}: {field} {x[field]:g} != {y[field]:g}')
        if sorted(x['events']) != sorted(y['events']):
            out.append(f'{name}: events differ')
        for node in sorted(set(x['nodes']) | set(y['nodes'])):
            p, q = x['nodes'].get(node, {}), y['nodes'].get(node, {})
            if (name, node.split('#')[0]) in dropped and not q:
                continue  # left out as the compiler warned
            for controller in sorted(set(p) | set(q)):
                if controller not in p or controller not in q:
                    out.append(f'{name}/{node}: {controller} only in the {"source" if controller in p else "binary"}'); continue
                told = _controller(controller, p[controller], q[controller])
                if told:
                    out.append(f'{name}/{node}/{controller}: {told}')
    return out


def dropped_nodes(warnings):
    """{(animation, node)} the compiler's warnings say it left out of the binary."""
    out = set()
    for warning in warnings:
        match = DROPPED.search(warning)
        if match:
            out |= {(match[1].lower(), node.strip().lower()) for node in match[2].split(',')}
    return out


# --- compiling --------------------------------------------------------------------------------------------------------

def _nvb():
    from tools.phenomorpher.phenomorpher.engine import neverblender_mdl
    return neverblender_mdl


def audit(binary, source_path, warnings):
    """'rig' when the decoder finds the binary as its source; 'round trip' when it needs the decompiled binary
    compared (an animation it cannot compare, a node name used twice); else a list of differences."""
    from tools.phenomorpher.phenomorpher.engine import rig_native
    try:
        result = rig_native.compare(binary, source_path, TOLERANCES)
    except ValueError as error:
        return 'round trip' if 'Ambiguous' in str(error) else [f'undecodable: {error}']
    if result['headerDifferences'] or result['staticRig']['differences']:
        return [f'{k}: {a} != {b}' for k, (a, b) in result['headerDifferences'].items()] + result['staticRig']['differences'][:5]
    return 'round trip' if result['failures'] else 'rig'


def toolchain(blender, addon):
    """NeverBlender's identity (`blender` and the add-on folder with its bundled cleanmodels), refused when either lacks."""
    require(blender and addon, 'A compile needs the Blender executable and the NeverBlender add-on folder (with cleanmodels)')
    return _nvb().toolchain(blender, addon)


def compile_models(repo, blender, addon, keys=None, timeout=3600):
    """Compile the sources `keys` ('<pack>/<name>.mdl'; default: every `stale` one) into their packs and pin each pair in
    the manifest. Every binary is audited first; one failure writes nothing. Returns {compiled, roundTrip, dropped}."""
    repo = Path(repo).resolve(); nvb = _nvb(); kept = sources(repo)
    keys = stale(repo) if keys is None else list(keys)
    unknown = sorted(set(keys) - set(kept)); require(not unknown, 'No source for ' + ', '.join(unknown[:5]))
    if not keys:
        return {'compiled': 0, 'roundTrip': 0, 'dropped': {}}
    tools = toolchain(blender, addon)
    packs = sorted({key.split('/')[0] for key in keys})
    lookups = [repo / SOURCES / pack for pack in packs] + [repo / pack for pack in packs]
    snapshot = {key: _sha(kept[key].read_bytes()) for key in keys}
    work = Path(tempfile.mkdtemp(prefix='tilekit-compile-', dir=repo / 'output' if (repo / 'output').is_dir() else None))
    try:
        jobs = []
        for key in keys:
            pack, name = key.split('/'); out = work / 'binary' / pack; out.mkdir(parents=True, exist_ok=True)
            jobs.append({'op': 'compile', 'input': kept[key], 'output': out / name, 'dirs': [kept[key].parent] + [d for d in lookups if d != kept[key].parent]})
        report = nvb.run(tools, jobs, timeout); rows, again, failed = {}, [], []
        for key, job, row in zip(keys, jobs, report['results']):
            require(row['sourceSha256'] == snapshot[key], f'{key}: the source changed while it was compiled')
            told = audit(job['output'], job['input'], row['warnings'])
            if isinstance(told, list):
                failed.append(f'{key}: ' + '; '.join(told))
            rows[key] = {'source': snapshot[key], 'binary': row['outputSha256'], 'bytes': row['bytes'], 'audit': told if isinstance(told, str) else 'failed',
                         'warnings': row['warnings']}
            if told == 'round trip':
                again.append((key, job['output'], work / 'back' / key))
        if again:
            for _, _, back in again:
                back.parent.mkdir(parents=True, exist_ok=True)
            nvb.run(tools, [{'op': 'decompile', 'input': binary, 'output': back, 'dirs': [binary.parent]} for _, binary, back in again], timeout)
            for key, _, back in again:
                dropped = dropped_nodes(rows[key]['warnings'])
                differences = round_trip(kept[key].read_bytes().decode('cp1252'), back.read_bytes().decode('cp1252', errors='replace'), dropped)
                if differences:
                    failed.append(f'{key}: decompiled again, ' + '; '.join(differences[:4]))
                if dropped:
                    rows[key]['dropped'] = sorted(f'{animation}/{node}' for animation, node in dropped)
        require(not failed, f'{len(failed)} compiled model(s) differ from their sources, nothing was written: ' + ' | '.join(failed[:6]))
        for key in keys:
            require(_sha(kept[key].read_bytes()) == snapshot[key], f'{key}: the source changed before the binaries were written')
        for key, job in zip(keys, jobs):  # every binary checked: now written
            pack, name = key.split('/'); shutil.copyfile(job['output'], repo / pack / name)
        told = manifest(repo); told['compiler'] = {'neverblender': tools['neverblender']['version'], 'cleanmodels': tools['cleanmodels'],
                                                   'blender': report.get('blenderVersion'), 'compilerSha256': tools['sha256']}
        for key in keys:
            told['models'][key] = {k: v for k, v in rows[key].items() if k != 'warnings'}
            told['models'][key]['compiled'] = datetime.date.today().isoformat()
        told['models'] = dict(sorted(told['models'].items()))
        (repo / MANIFEST).write_text(json.dumps(told, indent=1) + '\n', encoding='utf-8', newline='\n')
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {'compiled': len(keys), 'roundTrip': len(again), 'dropped': {key: rows[key]['dropped'] for key in keys if rows[key].get('dropped')}}


def adopt(repo, packs):
    """Copy every ASCII model of the tile packs `packs` to its source; the caller compiles them (`compile_models`).
    Returns the keys copied. A compiled pack model with no source is left as it is (envkit's own, compiled at build)."""
    from .inventory import compiled
    repo = Path(repo); moved = []
    for pack in packs:
        require(tile_pack(pack), f'{pack} is not a tile pack')
        for path in sorted((repo / pack).glob('*.mdl')):
            if compiled(path.read_bytes()):
                continue
            target = repo / SOURCES / pack / path.name; require(not target.exists(), f'{target} exists already')
            # copied: the pack keeps its ASCII copy until the compile, once every binary passed, writes over it
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target); moved.append(f'{pack}/{path.name}')
    return moved
