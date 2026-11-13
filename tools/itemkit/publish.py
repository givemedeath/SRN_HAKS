"""Publish user-approved itemkit weapons into the normal release packs (srn_weapon, srn_2da) and the comparison module.

    python -m tools.itemkit.publish ITEM=RUN [ITEM=RUN ...] --statement WORDS [--statement WORDS] --review TEXT
                                    --nwn-root DIR [--date YYYY-MM-DD] [--dry-run]

RUN is the item run directory the user approved: it holds the native package (native/attempt-*/native/native.json and its
HAK) and the fixture module whose blueprint shipped with it (fixture/attempt-*/fixture/userdir/modules/*.mod, or one
refixture-*/fixture/userdir/modules/*.mod). Every payload is copied byte for byte; nothing is regenerated.

The command refuses a name already in srn_weapon, checks the blueprint against the package (base item and the three
model parts), extends a carrier row's MaxRange only when an appearance number lies above it (that token and nothing
else), records the items, resources, sources and the user's words in docs/items/approved-weapons-v1.json, adds a male
and a female reviewer per blueprint to test-modules/weapon-waves (templates, placed instances, equip lines and the
generated sw_pairs.nss selector table), recompiles the module scripts, rebuilds srn_weapon, srn_2da and the module,
checks every built payload against its source file, refreshes the validation records and regenerates the combat
release manifest. --dry-run surveys and prints the plan without writing anything.

Publishing grants no production acceptance. The user's own words go in --statement; the client-review sentence in --review.
"""
import argparse
import copy
from dataclasses import dataclass, field
from datetime import date as Date
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import combat_release_manifest as crm  # the repository's GFF and 2DA readers
from tools import shared_tools

REPO = Path(__file__).resolve().parents[2]

PUBLICATION = Path('docs/items/approved-weapons-v1.json')
RELEASE_VALIDATION = Path('docs/items/approved-weapon-waves-release-validation.json')
BASEITEMS = Path('srn_2da/baseitems.2da')
WEAPONS = Path('srn_weapon')
MODULE_ROOT = Path('test-modules/weapon-waves')
MODULE = MODULE_ROOT/'module'
MODULE_ARCHIVE = 'sw_weapon_w2.mod'
BUILT = Path('output')
MODULE_BUILT = Path('output/weapon-waves-test')/MODULE_ARCHIVE
PAIRS_INCLUDE = 'sw_pairs.nss'
SCRIPTS = ('c.nss', 'sw_review.nss', 'sw2_enter.nss')
EXT = {3: 'tga', 2002: 'mdl', 2025: 'uti'}
TYPE = {v: k for k, v in EXT.items()}
GROUP_SIZE = 5                 # reviewer tags end in one digit 0-4 (sw<N>_m<i>)
ROW_Y = {'m': 5.0, 'f': 9.0}   # the southern row of the comparison area
ROW_STEP = 3.5
TILE = 10.0
REVIEWER = re.compile(r'^sw(\d+)_([mf])([0-4])$')
WORDS = ('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
         'seventeen eighteen nineteen').split()
TENS = 'twenty thirty forty fifty sixty seventy eighty ninety'.split()


class PublishError(ValueError):
    pass


def require(ok, message):
    if not ok: raise PublishError(message)


def sha(data): return hashlib.sha256(data).hexdigest()


def number_word(n):
    require(0 <= n < 100, f'No word for {n}')
    if n < 20: return WORDS[n]
    tens, ones = divmod(n, 10)
    return TENS[tens - 2] + ('-' + WORDS[ones] if ones else '')


def read_erf(source):
    """{(resref, type): bytes} of a HAK/MOD/ERF V1.0 archive (a path or its bytes)."""
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    require(len(data) >= 160 and data[4:8] == b'V1.0', f'Not an ERF V1.0 archive: {source if not isinstance(source, bytes) else "bytes"}')
    count = struct.unpack_from('<I', data, 16)[0]; keys, resources = struct.unpack_from('<II', data, 24)
    out = {}
    for i in range(count):
        resref, _, kind = struct.unpack_from('<16sIH', data, keys + 24*i)
        offset, size = struct.unpack_from('<II', data, resources + 8*i)
        out[(resref.rstrip(b'\0').decode('ascii').lower(), kind)] = data[offset:offset + size]
    return out


def load_exact(path):
    """JSON plus the ensure_ascii setting that reproduces its bytes (indent 2, trailing newline), so a rewrite keeps the format."""
    raw = Path(path).read_bytes(); data = json.loads(raw)
    for ascii_only in (False, True):
        if (json.dumps(data, indent=2, ensure_ascii=ascii_only) + '\n').encode('utf-8') == raw: return data, ascii_only
    raise PublishError(f'{path} is not in the indent-2 JSON form this command rewrites')


def dump(path, data, ascii_only):
    Path(path).write_bytes((json.dumps(data, indent=2, ensure_ascii=ascii_only) + '\n').encode('utf-8'))


@dataclass
class Package:
    item: str
    run: Path
    name: str
    blueprint: str
    base_item: int
    appearance: int
    hak: Path
    module: Path
    files: dict = field(default_factory=dict)     # srn_weapon file name -> (bytes, source archive)
    archives: dict = field(default_factory=dict)  # source archive name -> sha256, hashed once by survey


def one(paths, what):
    paths = sorted(paths)
    require(len(paths) == 1, f'Expected one {what}, found {len(paths)}: {[str(p) for p in paths]}')
    return paths[0]


def survey(item, run):
    """The approved package of one run: verified HAK, its resources and the blueprint from the fixture module."""
    run = Path(run)
    native_path = one(run.glob('native/attempt-*/native/native.json'), f'native.json under {run}')
    native = json.loads(native_path.read_text(encoding='utf-8'))
    hak = native_path.parent/Path(native['hak']['path']).name
    require(hak.is_file(), f'{item}: native HAK missing: {hak}')
    hak_bytes = hak.read_bytes()
    require(sha(hak_bytes) == native['hak']['sha256'], f'{item}: native HAK missing or changed: {hak}')
    modules = sorted(run.glob('fixture/attempt-*/fixture/userdir/modules/*.mod')) or sorted(run.glob('refixture-*/fixture/userdir/modules/*.mod'))
    module = one(modules, f'fixture module under {run}')
    blueprint = native['identity']['blueprint']
    module_bytes = module.read_bytes()
    uti = read_erf(module_bytes).get((blueprint, 2025))
    require(uti is not None, f'{item}: {module.name} has no blueprint {blueprint}.uti')
    fields = crm.parse_gff(uti)
    models = native['allocation']['models']
    require(set(models) == {'b', 'm', 't'}, f'{item}: this command publishes three-part (b/m/t) weapons; the package has {sorted(models)}')
    parts = [int(models[p].rsplit('_', 1)[1]) for p in ('b', 'm', 't')]
    require(fields.get('BaseItem') == native['baseItem'], f'{item}: blueprint base item {fields.get("BaseItem")} != package {native["baseItem"]}')
    require(len(set(parts)) == 1 and all(fields.get(f'ModelPart{i}') == parts[0] for i in (1, 2, 3)),
            f'{item}: blueprint model parts do not match the package models {models}')
    package = Package(item, run, native['identity']['displayName'], blueprint, native['baseItem'], parts[0], hak, module,
                      archives={hak.name: sha(hak_bytes), module.name: sha(module_bytes)})
    for (resref, kind), body in read_erf(hak_bytes).items():
        require(kind in EXT, f'{item}: unexpected resource type {kind} in {hak.name}')
        package.files[f'{resref}.{EXT[kind]}'] = (body, hak.name)
    package.files[f'{blueprint}.uti'] = (uti, module.name)
    return package


def table_row(lines, row):
    for index, line in enumerate(lines):
        tokens = line.split()
        if tokens and tokens[0] == str(row).encode(): return index
    raise PublishError(f'baseitems.2da has no row {row}')


def maxrange_needs(repo, packages):
    """{row: (current, required)} for carrier rows whose MaxRange lies below a new appearance number."""
    header, rows = crm.parse_2da((repo/BASEITEMS).read_text(encoding='latin-1'))
    needs = {}
    for p in packages:
        current = int(rows[p.base_item]['MaxRange'])            # plan() has checked every base item is a row
        if p.appearance > max(current, needs.get(p.base_item, (0, 0))[1]): needs[p.base_item] = (current, p.appearance)
    return needs


def extend_maxrange(table, needs):
    """The table bytes with only the MaxRange token of each needed row replaced; every other byte is kept."""
    lines = table.split(b'\n'); column = lines[2].split().index(b'MaxRange') + 1
    for row, (current, required) in needs.items():
        index = table_row(lines, row); line = lines[index]
        spans = [m.span() for m in re.finditer(rb'\S+', line)]; start, end = spans[column]
        require(int(line[start:end]) == current, f'Row {row} MaxRange changed while publishing')
        new = str(required).encode(); width = end - start
        if len(new) <= width: line = line[:start] + new + b' '*(width - len(new)) + line[end:]
        else:                                         # take padding after the token, keeping at least one space before the next
            extra = len(new) - width
            require(line[end:end + extra + 1] == b' '*(extra + 1), f'Row {row}: no padding to widen MaxRange to {required}')
            line = line[:start] + new + line[end + extra:]
        lines[index] = line
    return b'\n'.join(lines)


# --- comparison module -------------------------------------------------------------------------------------------

def groups_of(tags):
    """[(prefix, size)] of the placed reviewer groups in selector order, checked to be complete male/female pairs."""
    seen = {}
    for tag in tags:
        match = REVIEWER.match(tag)
        if match: seen.setdefault(int(match[1]), set()).add((match[2], int(match[3])))
    groups = []
    for number in sorted(seen):
        size = len({i for _, i in seen[number]})
        require(seen[number] == {(s, i) for s in 'mf' for i in range(size)}, f'Reviewer group sw{number}_ is not complete pairs 0..{size - 1}')
        groups.append((f'sw{number}_', size))
    require([int(p[2:-1]) for p, _ in groups] == list(range(1, len(groups) + 1)), 'Reviewer groups must be sw1_, sw2_, ... without gaps')
    return groups


def pairs_include(groups):
    """The generated NWScript selector table both c.nss and sw_review.nss include."""
    start, starts = 0, []
    for prefix, size in groups: starts.append((prefix, start, size)); start += size
    lines = ['// Generated by tools.itemkit.publish from the placed reviewers (sr_it_floor.git); do not edit by hand.',
             f'int SwPairCount(){{return {start};}}',
             'int SwGroupStart(string prefix){' + ''.join(f'if(prefix=="{p}")return {s};' for p, s, _ in starts) + 'return -1;}',
             'string SwPairPrefix(int pair){' + ''.join(f'if(pair<{s + n})return "{p}";' for p, s, n in starts) + 'return "";}']
    return '\n'.join(lines) + '\n'


def plan_pairs(creatures, packages, area_width):
    """New reviewer tags and positions: groups of up to five after the last group, continuing the southern row."""
    groups = groups_of(c['Tag']['value'] for c in creatures)
    row = [c['XPosition']['value'] for c in creatures if REVIEWER.match(c['Tag']['value']) and c['YPosition']['value'] == ROW_Y['m']]
    require(row, f'No male reviewer stands in the southern row (y {ROW_Y["m"]}) to continue from')
    x = max(row) + ROW_STEP; number = len(groups) + 1; pairs = []
    for start in range(0, len(packages), GROUP_SIZE):
        # c.nss and sw_review.nss read a reviewer's group as GetStringLeft(tag, 4): one digit, sw1_ to sw9_.
        require(number <= 9, f'Reviewer group sw{number}_ is past what the module selector can read (sw1_ to sw9_)')
        for index, package in enumerate(packages[start:start + GROUP_SIZE]):
            require(x <= area_width - ROW_STEP, f'No room left in the southern row for {package.item} (x {x})')
            pairs.append({'package': package, 'prefix': f'sw{number}_', 'index': index, 'x': x}); x += ROW_STEP
        number += 1
    return groups, pairs


def reviewer(template, tag, name, sex, x):
    """A template/instance copy for one reviewer: tag, resref, name and position change, nothing else."""
    record = copy.deepcopy(template)
    record['Tag']['value'] = tag; record['TemplateResRef']['value'] = tag
    record['FirstName']['value'] = {'0': f'{name} / {"male" if sex == "m" else "female"}'}
    record['XPosition']['value'] = x; record['YPosition']['value'] = ROW_Y[sex]
    return record


def enter_script(text, pairs, total):
    """sw2_enter.nss with the new blueprints given to the player, the new reviewers equipped and the pair count updated."""
    eol = '\r\n' if '\r\n' in text else '\n'      # the module scripts are stored -text with CRLF; keep the file's own endings
    lines = text.split(eol)
    give = next((i for i, l in enumerate(lines) if re.match(r'CreateItemOnObject\("[^"]+",pc\);SetLocalInt\(pc,"SW2_ITEMS"', l)), None)
    require(give is not None, 'sw2_enter.nss: the line that gives the player the last item and sets SW2_ITEMS was not found')
    lines[give:give] = [f'CreateItemOnObject("{p["package"].blueprint}",pc);' for p in pairs]
    equips = [i for i, l in enumerate(lines) if l.startswith('Equip("')]
    require(equips, 'sw2_enter.nss: no reviewer Equip lines were found'); tell = equips[-1] + 1
    lines[tell:tell] = [f'Equip("{p["prefix"]}{s}{p["index"]}","{p["package"].blueprint}",INVENTORY_SLOT_RIGHTHAND,0);' for p in pairs for s in 'mf']
    text = eol.join(lines)
    text, count = re.subn(r'SendMessageToPC\(pc,"[A-Za-z-]+ weapon/finish NPC pairs',
                          f'SendMessageToPC(pc,"{number_word(total).capitalize()} weapon/finish NPC pairs', text)
    require(count == 1, 'sw2_enter.nss: the pair-count message was not found once')
    return text


class Tools:
    def __init__(self, repo, nwn_root):
        self.repo, self.nwn_root = repo, nwn_root
        self.path = {name: shared_tools.resolve_tool(name, repo)['path'] for name in ('gff', 'script_comp', 'erf')}

    def run(self, name, *args, cwd=None):
        done = subprocess.run([self.path[name], *map(str, args)], cwd=cwd, capture_output=True, text=True)
        require(done.returncode == 0, f'{name} failed: {done.stdout[-2000:]}{done.stderr[-2000:]}')
        return done.stdout

    def to_json(self, path, folder):
        target = Path(folder)/(Path(path).name + '.json'); self.run('gff', '-i', path, '-o', target)
        return json.loads(target.read_text(encoding='utf-8'))

    def to_gff(self, data, path, folder):
        source = Path(folder)/(Path(path).name + '.json'); source.write_text(json.dumps(data), encoding='utf-8')
        self.run('gff', '-i', source, '-l', 'json', '-k', 'gff', '-o', path)

    def compile(self, folder, scripts):
        with tempfile.TemporaryDirectory() as user:
            self.run('script_comp', '--root', self.nwn_root, '--userdirectory', user, '--no-ovr', '-d', '.', '-c', *scripts, cwd=folder)


def add_reviewers(repo, packages, tools, work):
    """Reviewer templates and instances, equip lines and the selector table; returns the new tags and the pair total."""
    module = repo/MODULE
    git = tools.to_json(module/'sr_it_floor.git', work); area = crm.parse_gff((module/'sr_it_floor.are').read_bytes())
    creatures = git['Creature List']['value']
    groups, pairs = plan_pairs(creatures, packages, area['Width']*TILE)
    last = groups[-1][0]
    templates = {s: tools.to_json(module/f'{last}{s}0.utc', work) for s in 'mf'}
    placed = {c['Tag']['value']: c for c in creatures}
    for p in pairs:
        for s in 'mf':
            tag = f'{p["prefix"]}{s}{p["index"]}'
            require(tag not in placed and not (module/f'{tag}.utc').exists(), f'Reviewer {tag} already exists')
            tools.to_gff(reviewer(templates[s], tag, p['package'].name, s, p['x']), module/f'{tag}.utc', work)
            creatures.append(reviewer(placed[f'{last}{s}0'], tag, p['package'].name, s, p['x']))
    tools.to_gff(git, module/'sr_it_floor.git', work)
    groups = groups_of(c['Tag']['value'] for c in creatures); total = sum(n for _, n in groups)
    (module/PAIRS_INCLUDE).write_bytes(pairs_include(groups).encode('ascii'))
    enter = module/'sw2_enter.nss'
    enter.write_bytes(enter_script(enter.read_bytes().decode('ascii'), pairs, total).encode('ascii'))
    tools.compile(module, SCRIPTS)
    return [f'{p["prefix"]}{s}{p["index"]}' for p in pairs for s in 'mf'], total


# --- packs, payload checks and records ---------------------------------------------------------------------------

def rebuild(repo, tools):
    shell = shutil.which('pwsh') or shutil.which('powershell')
    require(shell, 'PowerShell is needed to run tools/Build-Haks.ps1')
    done = subprocess.run([shell, '-NoProfile', '-Command', "& ./tools/Build-Haks.ps1 -Pack @('srn_weapon','srn_2da') -SkipTlk"],
                          cwd=repo, capture_output=True, text=True)
    require(done.returncode == 0, 'Build-Haks failed: ' + done.stdout[-2000:] + done.stderr[-2000:])
    (repo/MODULE_BUILT).parent.mkdir(parents=True, exist_ok=True)
    tools.run('erf', '-c', '-e', 'MOD', '-f', repo/MODULE_BUILT, repo/MODULE)


def payload_exact(archive, folder, suffixes):
    """Every archive entry equals a source file of the folder and every source file is in the archive."""
    entries = sorted(read_erf(archive).values())
    sources = sorted(p.read_bytes() for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in suffixes)
    return entries == sources, len(entries)


def update_publication(repo, packages, needs, statements, review, policy):
    path = repo/PUBLICATION; pub, ascii_only = load_exact(path)
    families = {f['baseItemId']: f['id'] for f in pub['groupingPlan']['families']}
    for p in packages:
        require(p.base_item in families, f'{p.item}: base item {p.base_item} is not in the grouping plan')
        # The record's order: the item's package files by name, then its blueprint.
        for name, (body, archive) in sorted(p.files.items(), key=lambda f: (f[0].endswith('.uti'), f[0])):
            pub['resources'].append({'item': p.item, 'sourceArchive': archive, 'sourceResource': name, 'approvedSourceSha256': sha(body),
                                     'path': f'{WEAPONS.as_posix()}/{name}', 'sha256': sha(body), 'bytes': len(body),
                                     'resourceType': TYPE[name.rsplit('.', 1)[1]]})
        pub['items'].append({'id': p.item, 'name': p.name, 'blueprints': [p.blueprint], 'sourceArchive': p.hak.name,
                             'status': 'user-approved', 'family': families[p.base_item]})
        pub['sources'].update(p.archives)
    pub['approvalEvidence']['userStatements'] += [s for s in statements if s not in pub['approvalEvidence']['userStatements']]
    pub['clientReview'] += ' ' + review
    pub['blueprintPublicationPolicy'] += ' ' + policy
    if needs:
        table = sha((repo/BASEITEMS).read_bytes())
        for r in pub['resources']:
            if r['path'] == BASEITEMS.as_posix(): r['sha256'] = table
        pub['displayTable']['overrideSha256'] = table
        rows = {r['baseItem']: r for r in pub['additionalDisplayRows']}
        for row, (current, required) in sorted(needs.items()):
            if row == pub['displayTable']['baseItem']: pub['displayTable']['changes']['MaxRange']['after'] = str(required)
            elif row in rows: rows[row]['changes']['MaxRange']['after'] = str(required)
            else: pub['additionalDisplayRows'].append({'baseItem': row, 'changes': {'MaxRange': {'before': str(current), 'after': str(required)}}})
    dump(path, pub, ascii_only)
    return pub


def update_records(repo, packages, needs, statements, tags, total, today):
    weapons = repo/WEAPONS; built = {}
    for archive, folder, suffixes in ((repo/BUILT/'srn_weapon.hak', weapons, ('.tga', '.mdl', '.uti')),
                                      (repo/BUILT/'srn_2da.hak', repo/'srn_2da', ('.2da',)),
                                      (repo/MODULE_BUILT, repo/MODULE, None)):
        if suffixes is None: suffixes = tuple({p.suffix.lower() for p in Path(folder).iterdir() if p.is_file()})
        exact, count = payload_exact(archive, folder, suffixes)
        require(exact, f'{archive.name} does not carry exactly the files of {folder}')
        built[archive.name] = {'resources': count, 'sha256': sha(archive.read_bytes())}
    pub, _ = load_exact(repo/PUBLICATION)
    path = repo/RELEASE_VALIDATION; rv, ascii_only = load_exact(path)
    rv.update(weaponDesigns=len(pub['items']), blueprints=sum(len(i['blueprints']) for i in pub['items']),
              weaponResources=built['srn_weapon.hak']['resources'], publicationPins=len(pub['resources']),
              modelsDecoded=len(list(weapons.glob('*.mdl'))), imagesChecked=len(list(weapons.glob('*.tga'))))
    if 'updated' not in rv:
        items = list(rv.items()); at = [k for k, _ in items].index('date') + 1; rv = dict(items[:at] + [('updated', today)] + items[at:])
    rv['updated'] = today
    for entry in rv['builtArchives']:
        if entry['archive'] in built: entry.update(built[entry['archive']])
    for row, (current, required) in needs.items():
        rv['baseitemTableChanges'].setdefault(str(row), {'MaxRange': [str(current), str(required)]})['MaxRange'][1] = str(required)
    rv.setdefault('additions', []).append({'date': today, 'items': [p.item for p in packages], 'payloadsByteIdenticalToNativePackages': True,
                                           'rebuiltArchivesPayloadExact': True, 'baseitemTableChanged': bool(needs), 'comparisonReviewers': tags,
                                           'note': 'Published with tools.itemkit.publish. The new comparison reviewers were not run in that module\'s client.'})
    dump(path, rv, ascii_only)
    module_hash = built[MODULE_ARCHIVE]['sha256']
    path = repo/MODULE_ROOT/'manifest.json'; manifest, ascii_only = load_exact(path)
    manifest['releasePublication']['sha256'] = sha((repo/PUBLICATION).read_bytes())
    known = {r['path']: r for r in manifest['resources']}
    for f in sorted((repo/MODULE).iterdir()):
        rel = f.relative_to(repo).as_posix(); entry = {'sha256': sha(f.read_bytes()), 'bytes': f.stat().st_size}
        if rel in known: known[rel].update(entry)
        else: manifest['resources'].append({'path': rel, **entry})
    manifest.update(reviewerPairs=total, reviewerNPCs=2*total)
    dump(path, manifest, ascii_only)
    path = repo/MODULE_ROOT/'validation.json'; validation, ascii_only = load_exact(path)
    for entry in validation['archives']:
        if entry['archive'] == MODULE_ARCHIVE: entry.update(built[MODULE_ARCHIVE])
    validation['reviewers'].update(pairs=total, NPCs=2*total)
    approval = validation['clientApproval']
    numbers = [int(m[1] or 1) for m in (re.fullmatch(r'extension(\d*)', k) for k in approval) if m]   # 'extension' is the first
    key = 'extension' + str(max(numbers, default=0) + 1)
    approval[key] = {'date': today, 'addedPairs': len(tags)//2, 'status': 'items-approved-from-private-itemkit-fixtures',
                     'statements': statements, 'moduleSha256': module_hash,
                     'note': f'{", ".join(p.name for p in packages)} reviewer pairs were added ({", ".join(sorted({t.split("_")[0] + "_" for t in tags}))}). '
                             "They were not run in this module's client; each item was reviewed in its own itemkit fixture."}
    dump(path, validation, ascii_only)
    done = subprocess.run([sys.executable, '-B', 'tools/combat_release_manifest.py'], cwd=repo, capture_output=True, text=True)
    require(done.returncode == 0, 'combat_release_manifest failed: ' + done.stderr[-2000:])
    return built


def plan(repo, items):
    packages = [survey(item, run) for item, run in items]
    require(len({p.item for p in packages}) == len(packages), 'An item is listed twice')
    published = {f.name.lower() for f in (repo/WEAPONS).iterdir()}
    pub, _ = load_exact(repo/PUBLICATION)
    known = {i['id'] for i in pub['items']}
    names = [n for p in packages for n in p.files]
    clashes = sorted({n for n in names if n in published} | {n for n in names if names.count(n) > 1})
    require(not clashes, f'Already in srn_weapon or listed twice: {clashes}')
    require(not known & {p.item for p in packages}, f'Already published: {sorted(known & {p.item for p in packages})}')
    _, rows = crm.parse_2da((repo/BASEITEMS).read_text(encoding='latin-1'))
    missing = [p.item for p in packages if p.base_item not in rows]
    require(not missing, f'Base items not in {BASEITEMS.as_posix()}: {missing}')
    ranged = [p.item for p in packages if rows[p.base_item].get('RangedWeapon', '****') != '****']
    # The reviewer equip lines are melee lines (right hand, no ammunition); bows and firearms need theirs written by hand.
    require(not ranged, f'Ranged weapons are not published by this command: {ranged}')
    slots = {p.item: rows[p.base_item].get('EquipableSlots', '****') for p in packages}
    left = [item for item, value in slots.items() if value != '****' and not int(value, 16) & 0x10]
    require(not left, f'Items that cannot go in the right hand are not published by this command: {left}')   # 0x10: right hand
    return packages, maxrange_needs(repo, packages)


def publish(repo, items, statements, review, nwn_root, today=None, dry_run=False):
    repo = Path(repo).resolve(); today = today or Date.today().isoformat()
    require(statements and review, "Publishing needs the user's words (--statement) and the review sentence (--review)")
    packages, needs = plan(repo, items)
    summary = {'items': [{'id': p.item, 'name': p.name, 'blueprint': p.blueprint, 'baseItem': p.base_item, 'appearance': p.appearance,
                          'files': sorted(p.files)} for p in packages],
               'maxRange': {str(r): {'before': c, 'after': n} for r, (c, n) in needs.items()}}
    if dry_run: return {'dryRun': True, **summary}
    tools = Tools(repo, nwn_root)
    restore = snapshot(repo, packages)
    try:
        for p in packages:
            for name, (body, _) in p.files.items(): (repo/WEAPONS/name).write_bytes(body)
        if needs: (repo/BASEITEMS).write_bytes(extend_maxrange((repo/BASEITEMS).read_bytes(), needs))
        policy = (f'{", ".join(p.name for p in packages)}: blueprints and resources byte-identical to the approved itemkit packages'
                  + (''.join(f'; row {r} MaxRange {c}->{n}' for r, (c, n) in sorted(needs.items())) if needs else '; no table change') + '.')
        update_publication(repo, packages, needs, statements, review, policy)
        with tempfile.TemporaryDirectory() as work:
            tags, total = add_reviewers(repo, packages, tools, work)
        rebuild(repo, tools)
        built = update_records(repo, packages, needs, statements, tags, total, today)
    except BaseException:
        restore(); raise                          # the tracked tree is back as it was; built archives in output/ may be stale
    return {**summary, 'reviewers': tags, 'pairs': total, 'built': built}


def snapshot(repo, packages):
    """A function that puts every tracked file a publication touches back as it is now, and removes the files it adds."""
    records = [PUBLICATION, RELEASE_VALIDATION, BASEITEMS, MODULE_ROOT/'manifest.json', MODULE_ROOT/'validation.json',
               crm.JSON_OUT, crm.MD_OUT]
    saved = {repo/p: (repo/p).read_bytes() for p in records if (repo/p).is_file()}
    module = repo/MODULE
    if module.is_dir(): saved.update({f: f.read_bytes() for f in module.iterdir() if f.is_file()})
    created = [repo/WEAPONS/name for p in packages for name in p.files]

    def restore():
        for f in created: f.unlink(missing_ok=True)
        if module.is_dir():
            for f in module.iterdir():
                if f.is_file() and f not in saved: f.unlink()
        for f, body in saved.items(): f.write_bytes(body)
    return restore


def parse_item(text):
    item, sep, run = text.partition('=')
    if not sep or not item or not run: raise argparse.ArgumentTypeError('items are ITEM=RUN_DIR')
    return item, Path(run)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument('items', nargs='+', type=parse_item, help='ITEM=RUN_DIR')
    p.add_argument('--statement', action='append', default=[], help="the user's approval, in their words (repeatable)")
    p.add_argument('--review', help='the client-review sentence for the publication record')
    p.add_argument('--nwn-root', help='NWN:EE install (for the script compiler); not needed with --dry-run')
    p.add_argument('--date'); p.add_argument('--dry-run', action='store_true')
    a = p.parse_args(argv)
    if not a.dry_run and not a.nwn_root: p.error('--nwn-root is required unless --dry-run')
    result = publish(REPO, a.items, a.statement, a.review, a.nwn_root, a.date, a.dry_run)
    print(json.dumps(result, indent=1, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
