"""Publish client-reviewed head-library heads from a headbatch workspace into the repository, rerunning nothing.

Commands (see docs/heads/head-library-publication.md):
  stage   Resolve each head's final client session from the workspace checkpoints, take the exact MDL/PLT bytes that
          session's trial HAK loaded, check them against the head's native attempt, and write:
            REPO/srn_head/<slot>.mdl|.plt                  (refuses a different existing file)
            REPO/docs/heads/evidence/NAME/<slot>-client.jpg (cropped, reduced client frames)
            REPO/docs/heads/NAME.json                      (portable manifest: no local paths)
            OUT/NAME-draft.md                              (record draft; the author writes the exceptions)
          --dry-run writes the repository files under OUT/repo instead.
  verify  Check that a built HAK holds every resource of one or more manifests byte for byte.

Workspace conventions read here: runtime/batch-NN-checkpoint-M.json (heads[] with head, slot, design, clientEvidence
.session, corrections, geometrySubmissions, designSubmissions), trials/client-sessions/<session>/session.json ("trial"),
<trial>/runtime-manifest.json, <trial>/userdir/hak/*.hak, <trial>/README.md (actor table), the session's captures/,
heads/<head>/run/native/attempt-NN/native/resources, heads/<head>/run/export/attempt-NN/receipt.json,
design/records/<head>.json and spool/reviewed-rows.json.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

KIND = 'srn-head-library-publish-v1'
RESOURCE_TYPES = {'mdl': 2002, 'plt': 6}
TILE = (340, 320)
VIEWS = (('three', 'three-quarter right'), ('threeleft', 'three-quarter left'), ('backright', 'back right'),
         ('backleft', 'back left'), ('motion', 'talk/look motion'), ('alt', 'second look'))
CROPS = Path(__file__).with_name('library-crops.json')
REVIEW = ('Claude operator client review delegated by the user; user decisions quoted in reviewNotes. '
          'Exact client-reviewed native bytes; publication reruns nothing.')
RESREF = re.compile(r'[a-z0-9_]{1,16}')


class PublishError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PublishError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def erf_resources(data):
    """{(resref, type): bytes} of an ERF/HAK V1.0 or V1.1 archive."""
    require(data[:4] in (b'HAK ', b'ERF ', b'MOD ') and data[4:8] in (b'V1.0', b'V1.1'), 'Not an ERF V1.0/V1.1 archive')
    count, keys, offsets = (struct.unpack_from('<I', data, at)[0] for at in (16, 24, 28))
    width = 24 if data[4:8] == b'V1.0' else 40
    found = {}
    for i in range(count):
        key = data[keys+i*width:keys+(i+1)*width]
        name = key[:width-8].split(b'\0')[0].decode('ascii').lower()
        kind = struct.unpack_from('<H', key, width-4)[0]
        offset, size = struct.unpack_from('<II', data, offsets+i*8)
        require(offset+size <= len(data), f'{name}: resource past the end of the archive')
        found[(name, kind)] = data[offset:offset+size]
    return found


def checkpoint_order(path):
    match = re.search(r'batch-(\d+)-checkpoint-(\d+)\.json$', Path(path).name)
    return (int(match.group(2)), int(match.group(1))) if match else None


def latest_checkpoints(workspace, pattern):
    """Each head's row in the newest checkpoint that lists it, with that checkpoint's batch number."""
    latest = {}
    paths = [p for p in Path(workspace).glob(pattern) if checkpoint_order(p)]
    require(paths, f'No checkpoints match {pattern} in {workspace}')
    for path in sorted(paths, key=checkpoint_order):
        for row in read_json(path).get('heads') or []:
            if isinstance(row, dict) and 'head' in row:
                latest[row['head']] = dict(row, _checkpoint=path.name, _batch=checkpoint_order(path)[1])
    return latest


def select(latest, heads, prefix):
    if heads:
        require(len(set(heads)) == len(heads), 'A head is listed twice in --heads')
        missing = sorted(set(heads)-set(latest))
        require(not missing, 'Heads not in any checkpoint: '+', '.join(missing))
        return list(heads)
    chosen = sorted(h for h in latest if h.startswith(prefix or ''))
    require(chosen, f'No checkpointed heads start with {prefix!r}')
    return chosen


def resolve(workspace, head, row, override):
    """The final client session, its trial, the native attempt it packed and the exact bytes it loaded."""
    W = Path(workspace)
    session = override.get('session') or (row.get('clientEvidence') or {}).get('session')
    require(session, f'{head}: no client session in {row["_checkpoint"]} (give one with --overrides)')
    require(row.get('clientPassed', True) is not False, f'{head}: its checkpoint says the client review did not pass')
    trial = Path(read_json(W/session/'session.json')['trial'])
    slot = row.get('slot'); require(isinstance(slot, str) and RESREF.fullmatch(slot), f'{head}: bad slot {slot!r}')
    sources = native_sources(read_json(trial/'runtime-manifest.json'), head)
    require(len(sources) == 1, f'{head}: trial {trial.name} names native sources {sorted(sources)}, need exactly one')
    (folder, label), = sources.items()
    attempt = override.get('reviewedNativeAttempt') or label
    payload = {}
    for hak in sorted((trial/'userdir/hak').glob('*.hak')):
        resources = erf_resources(hak.read_bytes())
        for ext, kind in RESOURCE_TYPES.items():
            if (slot, kind) in resources:
                payload.setdefault(ext, []).append((hak.name, resources[(slot, kind)]))
    files = {}
    for ext in RESOURCE_TYPES:
        require(len(payload.get(ext, [])) == 1, f'{head}: {ext} {slot} is in {len(payload.get(ext, []))} trial HAKs, need one')
        native = (folder/'resources'/f'{slot}.{ext}').read_bytes()
        require(payload[ext][0][1] == native, f'{head}: trial {ext} differs from its native source ({label})')
        files[ext] = {'hak': payload[ext][0][0], 'data': native}
    require(files['mdl']['hak'] == files['plt']['hak'], f'{head}: MDL and PLT come from different trial HAKs')
    receipt = folder.parent/'receipt.json' if label.startswith('attempt-') else W/'heads'/head/'run/native'/attempt/'receipt.json'
    return {'head': head, 'slot': slot, 'session': session, 'trial': trial, 'attempt': attempt, 'files': files,
            'nativeReceipt': receipt if receipt.is_file() else None}


def export_receipt(workspace, head, native_receipt):
    """The export receipt the native attempt consumed (its sha256 is among the native receipt's inputs). A fit variant
    without a native receipt falls back to the newest export attempt."""
    exports = sorted((Path(workspace)/'heads'/head/'run/export').glob('attempt-*/receipt.json'))
    require(exports, f'{head}: no export attempt')
    if native_receipt is None:
        return exports[-1]
    pinned = {item.get('sha256') for item in read_json(native_receipt).get('inputs') or []}
    matched = [e for e in exports if sha256(e.read_bytes()) in pinned]
    require(len(matched) == 1, f'{head}: {len(matched)} export receipts are pinned by native {native_receipt.parent.name}, need one')
    return matched[0]


def native_sources(manifest, head):
    """{native folder: label} for HEAD in a trial's runtime manifest: heads/HEAD/run/native/attempt-NN/native
    ("attempt-NN") or a client fit variant .../fit-variants/TRIAL/HEAD/native ("fit-variant TRIAL")."""
    found = {}

    def visit(value):
        if isinstance(value, dict):
            for item in value.values(): visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
        elif isinstance(value, str):
            parts = list((PureWindowsPath if '\\' in value else PurePosixPath)(value).parts)  # parts[0] keeps the drive root
            for i in range(len(parts)-1):
                if parts[i] != head or parts[i-1:i] == ['client-sessions']:
                    continue
                if parts[i+1:i+3] == ['run', 'native'] and len(parts) > i+4 and parts[i+4] == 'native' \
                        and re.fullmatch(r'attempt-\d+', parts[i+3]):
                    found[Path(*parts[:i+5])] = parts[i+3]
                elif parts[i+1:i+2] == ['native'] and i >= 2 and parts[i-2] == 'fit-variants':
                    found[Path(*parts[:i+2])] = 'fit-variant '+parts[i-1]
    visit(manifest)
    return found


def actors(trial, head):
    """The two actors the trial README lists for HEAD (first and second look)."""
    rows = {}
    for line in (Path(trial)/'README.md').read_text(encoding='utf-8').splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 5 and cells[3] == head and cells[2].startswith('sr_h_actor') and cells[1].isdigit():
            rows[int(cells[1])] = cells[2]
    require(1 in rows and 2 in rows, f'{head}: trial README lists no first and second look actors')
    return rows[1], rows[2]


def crop_boxes(head, crops):
    family = head.rsplit('-', 1)[0]
    boxes = crops.get(family) or crops['default']
    require(isinstance(boxes, dict), f'{family}: crop boxes must be an object')
    require(set(boxes) == {v for v, _ in VIEWS}, f'{family}: crop boxes need exactly the views {[v for v, _ in VIEWS]}')
    return boxes


def gallery(workspace, resolved, crops, path):
    """Six cropped client frames (four angles, a motion frame and the second look) in one JPEG; returns its record."""
    from PIL import Image, ImageDraw
    head = resolved['head']; captures = Path(workspace)/resolved['session']/'captures'
    first, second = actors(resolved['trial'], head); boxes = crop_boxes(head, crops)
    tiles, frames = [], []
    for view, label in VIEWS:
        actor, name = (second, 'front') if view == 'alt' else (first, view)
        kind = 'motion' if view == 'motion' else 'inspect'
        found = sorted(captures.glob(f'*-{kind}-{actor}-{name}-*.png'))
        require(found, f'{head}: no {view} frame for {actor} in {captures}')
        frame = found[len(found)//2]
        image = Image.open(frame).convert('RGB')
        box = boxes[view]; require(0 <= box[0] < box[2] <= image.width and 0 <= box[1] < box[3] <= image.height,
                                   f'{head}: {view} crop {box} outside the {image.size} frame')
        tiles.append((image.crop(tuple(box)).resize(TILE, Image.LANCZOS), label))
        frames.append({'view': view, 'frame': frame.name, 'sha256': sha256(frame.read_bytes())})
    sheet = Image.new('RGB', (TILE[0]*3, (TILE[1]+22)*2), (16, 16, 16)); draw = ImageDraw.Draw(sheet)
    for i, (tile, label) in enumerate(tiles):
        x, y = (i % 3)*TILE[0], (i//3)*(TILE[1]+22)
        sheet.paste(tile, (x, y+22)); draw.text((x+6, y+5), label, fill=(230, 230, 230))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=82, optimize=True)
    return {'actors': [first, second], 'gallery': path.name, 'gallerySha256': sha256(path.read_bytes()), 'frames': frames}


def head_entry(workspace, row, resolved, evidence, rows, extra_notes):
    W = Path(workspace); head = resolved['head']
    design = read_json(W/'design/records'/f'{head}.json')
    export = read_json(export_receipt(W, head, resolved['nativeReceipt']))['result']
    material = export.get('nativeMaterial')
    if isinstance(material, dict):
        material = {k: material[k] for k in ('policy', 'applied', 'material', 'channels', 'reason') if k in material}
    notes = [n for n in (row.get('corrections') or []) if isinstance(n, str)] + list(extra_notes)
    entry = {
        'head': head, 'design': design.get('name') or row.get('design'), 'batch': row['_batch'], 'slot': resolved['slot'],
        'resources': {ext: {'name': f"{resolved['slot']}.{ext}", 'sha256': sha256(f['data']), 'bytes': len(f['data'])}
                      for ext, f in resolved['files'].items()},
        'triangles': export.get('triangles'), 'nativeMaterial': material, 'paletteRows': rows.get(head),
        'features': design.get('features'), 'designSha256': (design.get('design') or {}).get('sha256'),
        'designSource': {k: design.get(k) for k in ('generator', 'sourceHead', 'sourceDraft')},
        'geometrySubmissions': row.get('geometrySubmissions'), 'designSubmissions': row.get('designSubmissions'),
        'reviewedNativeAttempt': resolved['attempt'],
        'clientEvidence': {'session': Path(resolved['session']).name, 'trialHak': resolved['files']['mdl']['hak'], **evidence},
        'reviewNotes': notes,
    }
    if entry['designSubmissions'] is None:
        del entry['designSubmissions']
    require(entry['paletteRows'] is not None and entry['triangles'] is not None, f'{head}: palette rows or triangles missing')
    return entry


def draft(manifest, name, existing):
    """A record draft: the slot table, galleries and loading note. Exceptions and limitations are the author's."""
    def hair(h):
        text = ((h.get('features') or {}).get('hair') or '').split(';')[0].split(',')[0].strip().rstrip('.')
        return text[:1].upper()+text[1:] if text else '-'
    def family(h):
        return h['head'].rsplit('-', 1)[0].replace('-', ' ').capitalize()
    rows = '\n'.join(f"| {h['design']} | {family(h)} | `{h['slot']}` | {hair(h)} | "
                     + ' / '.join(str((h['paletteRows'] or {}).get(c)) for c in ('0', '1', '8', '9')) + ' |'
                     for h in manifest['heads'])
    gallery = '\n\n'.join(f"![{h['design']} ({h['slot']}) in the client](evidence/{name}/{h['clientEvidence']['gallery']})"
                          for h in manifest['heads'])
    return f"""# Head library: {len(manifest['heads'])} client-reviewed heads

| Name | Race | Slot/model | Hair | Skin / hair / iris / tattoo2 rows |
| --- | --- | --- | --- | --- |
{rows}

Each head is the exact native bytes the private NWN:EE client loaded in its final review session, taken from that
session's trial HAK; publication reruns nothing. The [portable manifest]({name}.json) holds resource and design hashes,
the client session and trial HAK, the hash of every source frame used in the galleries and the review notes.

## User-accepted exceptions and known limitations

(Write these from the manifest's reviewNotes: quality exceptions, geometry, colour, cyberware. Quote the user's words.)

## In-game evidence

These galleries crop and reduce the original client frames; textures and geometry are not edited. Each shows four angles,
a motion frame and the second look.

{gallery}

## Loading

Load `srn_head` above `srn_body` and use the slots above. All {existing} existing `srn_head` resources remain
byte-identical.
"""


def write_new(path, data):
    """Write bytes, or accept an identical existing file; refuse a different one."""
    path = Path(path)
    if path.exists():
        require(path.read_bytes() == data, f'{path} exists with different bytes')
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def stage(args):
    W, repo, out = Path(args.workspace), Path(args.repo), Path(args.out)
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', args.name), '--name is a lowercase file stem, e.g. head-library-trolls-v1')
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', args.created), '--created takes YYYY-MM-DD')
    crops = read_json(args.crops or CROPS)
    overrides = read_json(args.overrides) if args.overrides else {}
    latest = latest_checkpoints(W, args.checkpoints)
    heads = select(latest, args.heads.split(',') if args.heads else None, args.prefix)
    rows = read_json(W/'spool/reviewed-rows.json')
    target = out/'repo' if args.dry_run else repo
    head_folder = repo/'srn_head'
    manifest_path = target/'docs/heads'/f'{args.name}.json'
    require(not manifest_path.exists(), f'{manifest_path} exists; publish under a new name')
    evidence = target/'docs/heads/evidence'/args.name
    sheets = out/'galleries'  # nothing reaches the repository until every head has resolved
    staged, entries = [], []
    for head in heads:
        row = latest[head]; override = overrides.get(head, {})
        resolved = resolve(W, head, row, override)
        for ext, f in resolved['files'].items():
            current = head_folder/f"{resolved['slot']}.{ext}"
            require(not current.exists() or current.read_bytes() == f['data'], f'{current} exists with different bytes')
        record = gallery(W, resolved, crops, sheets/f"{resolved['slot']}-client.jpg")
        entries.append(head_entry(W, row, resolved, record, rows, override.get('reviewNotes', [])))
        staged.append(resolved)
        print(head, resolved['slot'], resolved['attempt'], resolved['files']['mdl']['hak'], record['gallery'])
    slots = [e['slot'] for e in entries]
    require(len(set(slots)) == len(slots), 'Two heads share a slot')
    manifest = {'kind': KIND, 'created': args.created, 'heads': entries, **({'notes': args.notes} if args.notes else {}),
                'review': REVIEW}
    text = json.dumps(manifest, indent=1, ensure_ascii=False)+'\n'
    names = {f"{r['slot']}.{ext}" for r in staged for ext in r['files']}
    existing = len([p for p in head_folder.iterdir() if p.is_file() and p.name not in names]) if head_folder.is_dir() else 0
    writes = [(target/'srn_head'/f"{r['slot']}.{ext}", f['data']) for r in staged for ext, f in r['files'].items()]
    writes += [(evidence/f"{r['slot']}-client.jpg", (sheets/f"{r['slot']}-client.jpg").read_bytes()) for r in staged]
    for path, data in writes:  # every target is checked before the first write
        require(not path.exists() or path.read_bytes() == data, f'{path} exists with different bytes')
    require(not re.search(r'[A-Za-z]:[\\/]|\\\\|"/|\s/(home|Users|mnt|tmp|var|srv)/', text), 'The manifest would hold a local path')
    for path, data in writes:
        write_new(path, data)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(text, encoding='utf-8', newline='\n')
    out.mkdir(parents=True, exist_ok=True)
    (out/f'{args.name}-draft.md').write_text(draft(manifest, args.name, existing), encoding='utf-8', newline='\n')
    print(json.dumps({'heads': len(entries), 'manifest': manifest_path.as_posix(), 'draft': (out/f'{args.name}-draft.md').as_posix()}))
    return 0


def verify(args):
    resources = erf_resources(Path(args.hak).read_bytes())
    checked = 0
    for path in args.manifest:
        manifest = read_json(path)
        require(manifest.get('kind') == KIND, f'{path}: not a {KIND} manifest')
        for head in manifest['heads']:
            for ext, meta in head['resources'].items():
                data = resources.get((head['slot'], RESOURCE_TYPES[ext]))
                require(data is not None, f"{path}: {meta['name']} is not in {args.hak}")
                require(sha256(data) == meta['sha256'] and len(data) == meta['bytes'], f"{path}: {meta['name']} differs from its manifest")
                checked += 1
    print(json.dumps({'hak': Path(args.hak).name, 'resources': checked, 'passed': True}))
    return 0


def parser():
    top = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    commands = top.add_subparsers(dest='command', required=True)
    p = commands.add_parser('stage', help='stage client-reviewed heads into the repository')
    p.add_argument('--workspace', required=True, help='headbatch workspace folder')
    p.add_argument('--repo', required=True, help='repository checkout to write into')
    p.add_argument('--name', required=True, help='record stem, e.g. head-library-trolls-v1')
    p.add_argument('--created', required=True, help='publication date, YYYY-MM-DD')
    which = p.add_mutually_exclusive_group(required=True)
    which.add_argument('--heads', help='comma-separated head names')
    which.add_argument('--prefix', help='every checkpointed head whose name starts with this, e.g. troll-')
    p.add_argument('--checkpoints', default='runtime/batch-*-checkpoint-*.json', help='checkpoint glob in the workspace')
    p.add_argument('--crops', type=Path, help=f'gallery crop boxes per head family (default {CROPS.name})')
    p.add_argument('--overrides', type=Path, help='JSON {head: {session?, reviewNotes?, reviewedNativeAttempt?}} for heads whose checkpoint lacks them')
    p.add_argument('--notes', help='manifest-level note, e.g. how designSubmissions was recorded')
    p.add_argument('--out', required=True, help='folder for the record draft (and the repository files with --dry-run)')
    p.add_argument('--dry-run', action='store_true', help='write the repository files under OUT/repo instead')
    p.set_defaults(handler=stage)
    p = commands.add_parser('verify', help='check a built HAK against publication manifests')
    p.add_argument('--hak', required=True); p.add_argument('--manifest', required=True, action='append')
    p.set_defaults(handler=verify)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except (PublishError, OSError, KeyError, json.JSONDecodeError) as error:
        print('REFUSED:', error if isinstance(error, PublishError) else f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
