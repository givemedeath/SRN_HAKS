"""Paint a tileset's groups in the Toolset one by one and read back what it saved: the palette lists each, it goes down
whole, and its keyed door hooks make their doors (the srx01 check of 2026-11-24, docs/tilesets/srx01-plan.md).

  python -m tools.envkit.toolset_paint prepare --tileset srx01 --user <fresh folder> --game <game> [--only 3,57]
  python -m tools.envkit.toolset_paint run     --user <folder>
  python -m tools.envkit.toolset_paint read    --user <folder>
  python -m tools.envkit toolset retire --user <folder>

`prepare` lays one area for each ground the groups stand in: a group goes down only where the ground meets its edges.
Start the Toolset as it says, size it (`Toolset.ps1 -Do move`), open the module, expand its tree, then start `run` in
the background: it opens each area, arms each group from the palette, waits for one click, saves, keeps the module and
undoes. **The clicks are real ones**, by computer use, on an empty tile of the area view, one about every four seconds
(posted clicks are not painted); a click at another time only selects a tile. Run it only while no game client is up:
computer use hides other windows. `run` drives only the Toolset started on its folder, tries again what was not whole,
and stops at tiles an undo left. `read` says what each saved module holds.

What the Toolset does, found by trying: File > Save has no shortcut, but Save and Undo answer their menu messages; a
feature of one tile stays armed after it is painted, so the saved file is what is judged, not the mode; another
group's tiles are not painted over; a hook of the generic door type 0 makes no door."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from . import require, toolset

OPEN = ('Grass', 'Concrete', 'Harbor', 'Arcology_Void')  # the ground a group of mixed ground is tried on, the first it has
SAVE, UNDO = 47, 56  # the Toolset's menu commands (v89.8193.37-17)
OTHERS = 'tiles of another group: '
CLICK = ((0x200, 0), (0x201, 1), (0x202, 0))  # move, down, up


def plan(set_text, palette, only=None):
    """{'grounds': [[terrain, fill tile]], 'groups': [{number, name, ground, tiles, doors}]}: each group of the set (or
    those numbered in `only`) with its palette name, the ground it is tried on and the keyed doors it makes. palette:
    {model of the first tile, lower case: the name shown}. A fill is a plain tile of one ground that is no group's own,
    since the Toolset paints nothing over a group (a tower's tile was the fill once, 2026-11-24)."""
    from tools.tilekit import inventory
    read = inventory.read_set(set_text)
    tiles = {tile['number']: tile for tile in read['tiles']}
    keyed = {}
    for name, held in inventory.sections(set_text):
        if name.upper().startswith('TILE') and 'DOOR' in name.upper() and int(held.get('Type') or 0):
            keyed.setdefault(int(name.upper()[4:].split('DOOR')[0]), []).append(int(held['Type']))
    own = {number for group in read['groups'] for number in group['tiles']}
    fills = {}
    for tile in read['tiles']:
        plain = len(set(tile['corners'])) == 1 and len(set(tile['heights'])) == 1 and not any(tile['crossers']) and not tile['doors']
        if plain and tile['number'] not in own:
            fills.setdefault(tile['corners'][0], tile['number'])
    unknown = sorted(set(only or ()) - set(range(len(read['groups']))))
    require(not unknown and (only is None or only), 'The set has no group ' + (', '.join(map(str, unknown)) or 'chosen'))
    groups = []
    for number, group in enumerate(read['groups']):
        if only is not None and number not in only:
            continue
        held = [one for one in group['tiles'] if one in tiles]
        corners = Counter(corner for one in held for corner in tiles[one]['corners'])
        shown = next((palette[tiles[one]['model'].lower()] for one in held if tiles[one]['model'].lower() in palette), None)
        require(shown, f'The palette does not list group {number}, {group["name"]}')
        choices = [terrain for terrain in OPEN if terrain in corners and terrain in fills] if len(corners) > 1 else []
        choices += [terrain for terrain, _ in corners.most_common() if terrain in fills]
        require(choices, f'No plain tile of the ground of group {number}, {group["name"]}')
        groups.append({'number': number, 'name': shown, 'ground': choices[0], 'tiles': held, 'doors': sorted(door for one in held for door in keyed.get(one, []))})
    names = Counter(group['name'] for group in groups)
    require(all(count == 1 for count in names.values()), 'The palette shows one name twice')
    grounds = list(dict.fromkeys(group['ground'] for group in groups))
    general = next((held for name, held in inventory.sections(set_text) if name.upper() == 'GENERAL'), {})
    start = None
    if str(general.get('Interior', '0')).strip() == '1':  # an interior's ground is its walls, where no start point stands
        floors = [terrain for terrain in read['terrains'] if terrain in fills and terrain not in grounds]
        require(floors, 'No plain floor tile for the start point of an interior')
        start = fills[floors[0]]
    return {'grounds': [[terrain, fills[terrain]] for terrain in grounds], 'groups': groups, 'start': start}


def packs(repo, set_text, own):
    """The tile packs holding the models of a set's tiles other than its own pack: a merged set's families (srx02's
    tiles are in srn_t_udp2, srn_t_tfb01, srn_t_tbx78 and srn_t_nac01). Without them the Toolset falls over on the
    first group armed, with an access violation (2026-11-28)."""
    from tools.tilekit import inventory
    models = {tile['model'].lower() for tile in inventory.read_set(set_text)['tiles']}
    found = []
    for folder in sorted(Path(repo).glob('srn_t_*')):
        if folder.name == own or not folder.is_dir():
            continue
        held = {one.stem.lower() for place in (folder, Path(repo) / 'sources' / folder.name) if place.is_dir() for one in place.glob('*.mdl')}
        if models & held:
            found.append(folder.name)
    return found


def area_name(planned, ground):
    return f'ekt{[one for one, _ in planned["grounds"]].index(ground):02d}'


def judge(planned, group, laid, doors):
    """What is wrong with a painted group, from its saved area's tile numbers and its doors' appearances: [words]."""
    want, got, wrong = Counter(group['tiles']), Counter(laid), []
    short = sorted(tile for tile, count in want.items() if got[tile] < count)
    if short:
        wrong.append('tiles missing: ' + ', '.join(map(str, short)))
    if sorted(doors) != group['doors']:
        wrong.append(f'doors {sorted(doors)}, not {group["doors"]}')
    strangers = {tile for other in planned['groups'] if other['number'] != group['number'] for tile in other['tiles']} - set(group['tiles'])
    left = sorted(strangers & set(laid))
    if left:
        wrong.append(OTHERS + ', '.join(map(str, left)))
    return wrong


def _gff(path):
    return json.loads(toolset._tools()('nwn_gff', ['-i', path, '-k', 'json']))


def prepare(repo, tileset, user, haks, *, game=None, only=None, size=16):
    repo, user = Path(repo).resolve(), Path(user).resolve()
    folder = repo / f'srn_t_{tileset}'
    document = _gff(folder / f'{tileset}palstd.itp')
    palette = {one['RESREF']['value'].lower(): one['NAME']['value'] for part in document['MAIN']['value'][:2] for one in part['LIST']['value']}
    text = (folder / f'{tileset}.set').read_bytes().decode('cp1252')
    haks = tuple(dict.fromkeys((folder.name, *packs(repo, text, folder.name), *haks)))  # srx01's pack is none of the usual ones
    planned = plan(text, palette, only)
    made, before = None, dict(toolset.AREAS)
    try:
        for ground, fill in planned['grounds']:
            name = area_name(planned, ground)
            toolset.AREAS[tileset] = (name, f'{name[3:]} {ground}', fill)
            one = toolset.documents((tileset,), haks, toolset.TLK, size)
            if made is None:
                made = one
            else:
                made.update({key: value for key, value in one.items() if key.startswith(name)})
                made['module.ifo']['Mod_Area_list']['value'] += one['module.ifo']['Mod_Area_list']['value']
    finally:
        toolset.AREAS.clear()
        toolset.AREAS.update(before)
    if planned.get('start') is not None:  # the start point is on the first area's south-west corner tile (toolset.START)
        first = area_name(planned, planned['grounds'][0][0]) + '_a.are'
        made[first]['Tile_List']['value'][0]['Tile_ID']['value'] = planned['start']
    told = toolset.prepare(user, repo / 'output', haks=haks, game=game, made=made)
    (user / 'paint.json').write_text(json.dumps(planned), encoding='utf-8')
    return {**told, 'groups': len(planned['groups']), 'areas': len(planned['grounds'])}


def judged(planned, group, module):
    """What is wrong with a group in a module the Toolset saved."""
    with tempfile.TemporaryDirectory() as out:
        toolset._tools()('nwn_erf', ['-x', '-f', Path(module).resolve()], cwd=out)
        base = Path(out) / (area_name(planned, group['ground']) + '_a')
        are, git = _gff(base.with_suffix('.are')), _gff(base.with_suffix('.git'))
    return judge(planned, group, [tile['Tile_ID']['value'] for tile in are['Tile_List']['value']], [door['Appearance']['value'] for door in git['Door List']['value']])


def keep(planned, group, module, out):
    """Keep a saved module if its group is whole, so that another is tried again when `run` is; what is wrong with it.
    Another group's tiles stop the run: an undo did nothing, or a paint was left by a run that was stopped."""
    wrong = judged(planned, group, module)
    require(not any(word.startswith(OTHERS) for word in wrong), f'{group["name"]}: {"; ".join(wrong)}: an earlier paint was not undone. Undo in the Toolset until the area is plain, then run again')
    if not wrong:
        shutil.copyfile(module, Path(out) / f'{group["number"]}.mod')
    return wrong


def started_on(command_line, user):
    """Whether a Toolset's command line has it on the user folder `user`: any other Toolset is another session's, and
    its module has this one's name."""
    plain = lambda text: str(text).replace('/', '\\').rstrip('\\').lower()
    found = re.search(r'(?i)\s-userdirectory\s+(?:"([^"]+)"|(.+?))\s*$', command_line or '')
    return bool(found) and plain(found.group(1) or found.group(2)) == plain(user)


def read(user):
    """[{number, name, wrong: [words]}] of the saved modules, and the groups with none."""
    user = Path(user).resolve()
    planned, told = json.loads((user / 'paint.json').read_text(encoding='utf-8')), []
    for group in planned['groups']:
        module, wrong = user / 'painted' / f'{group["number"]}.mod', ['not painted']
        if module.is_file():
            wrong = judged(planned, group, module)
        told.append({'number': group['number'], 'name': group['name'], 'wrong': wrong})
    return told


class Window:
    """The running Toolset, by window messages. Its palette's items are read and armed here; the painting is not."""

    def __init__(self, user):
        import ctypes
        import struct
        from ctypes import wintypes as w
        self.c, self.w, self.struct = ctypes, w, struct
        self.u, self.k = ctypes.WinDLL('user32'), ctypes.WinDLL('kernel32')
        pointer, size = ctypes.c_void_p, ctypes.c_size_t
        self.u.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, size, ctypes.c_ssize_t, w.UINT, w.UINT, ctypes.POINTER(size)]
        self.u.SendMessageTimeoutW.restype = ctypes.c_ssize_t
        self.u.PostMessageW.argtypes = [w.HWND, w.UINT, size, ctypes.c_ssize_t]
        self.k.OpenProcess.restype = w.HANDLE
        self.k.VirtualAllocEx.restype = pointer
        self.k.VirtualAllocEx.argtypes = [w.HANDLE, pointer, size, w.DWORD, w.DWORD]
        for name in ('WriteProcessMemory', 'ReadProcessMemory'):
            getattr(self.k, name).argtypes = [w.HANDLE, pointer, pointer, size, pointer]
        self.walker = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        found = [one for one in self.tops() if self.cls(one) == 'TfrmFrame' and 'Neverwinter Nights Toolset' in self.text(one)]
        require(len(found) == 1, f'One running Toolset is needed, not {len(found)}')
        self.frame = found[0]
        self.pid = self.owner(self.frame)
        asked = f'(Get-CimInstance Win32_Process -Filter "ProcessId={self.pid}").CommandLine'
        line = subprocess.run(['powershell', '-NoProfile', '-Command', asked], capture_output=True, text=True).stdout
        require(started_on(line, user), f'The running Toolset was not started on {user}: it is another\'s, and is left alone')
        self.process = self.k.OpenProcess(0x0438, False, self.pid)  # read, write and allocate its memory: a tree wants its structures there
        self.memory = self.k.VirtualAllocEx(self.process, None, 4096, 0x3000, 4)
        require(self.memory and self.memory < 2 ** 31, 'No memory in the Toolset')

    def _walk(self, call, *first):
        out = []
        call(*first, self.walker(lambda handle, _: out.append(handle) or True), 0)
        return out

    def tops(self):
        return self._walk(self.u.EnumWindows)

    def kids(self, of=None):
        return self._walk(self.u.EnumChildWindows, of or self.frame)

    def cls(self, handle):
        held = self.c.create_unicode_buffer(256)
        self.u.GetClassNameW(handle, held, 256)
        return held.value

    def text(self, handle):
        held = self.c.create_unicode_buffer(512)
        self.u.GetWindowTextW(handle, held, 512)
        return held.value

    def owner(self, handle):
        held = self.w.DWORD()
        self.u.GetWindowThreadProcessId(handle, self.c.byref(held))
        return held.value

    def rect(self, handle):
        held = self.w.RECT()
        self.u.GetWindowRect(handle, self.c.byref(held))
        return held.left, held.top, held.right, held.bottom

    def visible(self, kind, of=None):
        return [one for one in self.kids(of) if self.cls(one) == kind and self.u.IsWindowVisible(one)]

    def send(self, handle, message, first=0, second=0):
        held = self.c.c_size_t()
        require(self.u.SendMessageTimeoutW(handle, message, first, second, 2, 60000, self.c.byref(held)), 'The Toolset does not answer')
        return held.value

    def write(self, data):
        self.k.WriteProcessMemory(self.process, self.memory, data, len(data), None)

    def read(self, offset, count):
        held = self.c.create_string_buffer(count)
        self.k.ReadProcessMemory(self.process, self.memory + offset, held, count, None)
        return held.raw

    def post(self, handle, messages, x, y, wait=0.15):
        for message, held in messages:
            self.u.PostMessageW(handle, message, held, (y << 16) | (x & 0xFFFF))
            time.sleep(wait)

    def status(self):
        bar = self.visible('TStatusBar')[0]
        self.write(bytes(256))
        self.send(bar, 0x402, 1, self.memory)
        return self.read(0, 128).split(bytes(1))[0].decode('cp1252')

    def label(self, tree, item):
        self.write(self.struct.pack('<IIIIIiiiii', 1, item, 0, 0, self.memory + 64, 256, 0, 0, 0, 0))  # a 32-bit TVITEM
        self.send(tree, 0x110C, 0, self.memory)
        return self.read(64, 256).split(bytes(1))[0].decode('cp1252')

    def items(self, tree, of=None):
        """The children of an item of a tree, or its top items."""
        out, one = [], self.send(tree, 0x110A, 0 if of is None else 4, of or 0)
        while one:
            out.append(one)
            one = self.send(tree, 0x110A, 1, one)
        return out

    def show(self, tree, item):
        """Show and select an item, and say where it is: (x, y)."""
        self.send(tree, 0x1114, 0, item)
        self.send(tree, 0x110B, 9, item)
        self.write(self.struct.pack('<I12x', item))
        self.send(tree, 0x1104, 1, self.memory)
        left, top, _, bottom = self.struct.unpack('<4i', self.read(0, 16))
        return left + 8, (top + bottom) // 2

    def palette(self):
        shown = self.visible('TfraMainPalette')[0]
        tree = max(self.visible('TTreeView', shown), key=lambda one: self.rect(one)[3] - self.rect(one)[1])
        return tree, {self.label(tree, one): one for top in self.items(tree)[:2] for one in self.items(tree, top)}

    def command(self, number):
        self.u.PostMessageW(self.frame, 0x111, number, 0)

    def others(self):
        shown = [one for one in self.tops() if self.owner(one) == self.pid and self.u.IsWindowVisible(one)]
        return [(self.cls(one), self.text(one)) for one in shown if self.cls(one) not in ('TfrmFrame', 'TApplication', 'THintWindow')]

    def disarm(self):
        bar = next((one for one in self.visible('TToolBar') if abs(self.rect(one)[2] - self.rect(one)[0] - 80) < 4), None)  # the selection modes
        require(bar, 'The Toolset shows no selection mode buttons')
        for _ in range(6):
            if self.status() == 'Select':
                return
            self.post(bar, CLICK, 20, 11)
            time.sleep(0.6)
        require(False, 'The Toolset stays in ' + self.status())

    def arm(self, tree, item):
        self.disarm()
        for _ in range(3):
            self.post(tree, CLICK, *self.show(tree, item))
            time.sleep(2)
            if self.status() == 'Paint':
                return True
        return False

    def open_area(self, name, title):
        tree = self.visible('TTreeView', self.visible('TfraMainInventory')[0])[0]
        top = self.items(tree)
        require(top and self.items(tree, top[0]), 'No module is open in the Toolset')
        areas = top[0]
        for one in self.items(tree, areas):
            self.send(tree, 0x1102, 1, one)
        x, y = self.show(tree, next(one for one in self.items(tree, areas) if self.label(tree, one) == title))
        self.post(tree, ((0x201, 1), (0x202, 0), (0x203, 1), (0x202, 0)), x, y, 0.05)
        end = time.time() + 120
        while time.time() < end:
            time.sleep(1)
            if any(self.text(one).endswith(name + '_a') for one in self.visible('TfrmViewerArea')):
                time.sleep(3)
                return
        require(False, 'The area did not open: ' + title)

    def clicked(self, limit=300):
        """Wait for a real click of the left button while the Toolset is in front."""
        self.u.GetAsyncKeyState(1)
        end = time.time() + limit
        while time.time() < end:
            if self.u.GetAsyncKeyState(1) & 0x8001 and self.owner(self.u.GetForegroundWindow()) == self.pid:
                return True
            time.sleep(0.02)
        return False

    def save(self, module):
        before = os.path.getmtime(module)
        self.command(SAVE)
        end = time.time() + 20
        while time.time() < end and os.path.getmtime(module) == before:
            time.sleep(0.1)
        end, quiet = time.time() + 30, time.time()
        while time.time() < end and time.time() - quiet < 0.8:  # it shows several progress windows in turn
            if any(kind == 'TdlgProgress' for kind, _ in self.others()):
                quiet = time.time()
            time.sleep(0.1)
        return os.path.getmtime(module) != before

    def undo(self):
        """Undo all that was painted: a click at each try to arm a group paints it again, and with nothing left to undo
        the Toolset does nothing."""
        for _ in range(5):
            self.command(UNDO)
            time.sleep(0.3)


def no_client():
    running = subprocess.run(['tasklist'], capture_output=True, text=True).stdout.lower()
    require('nwmain.exe' not in running, 'A game client is running: wait for it, and make no clicks')


def run(user):
    user = Path(user).resolve()
    planned = json.loads((user / 'paint.json').read_text(encoding='utf-8'))
    module, out = user / 'modules' / f'{toolset.MODULE}.mod', user / 'painted'
    out.mkdir(exist_ok=True)
    no_client()
    window, unwhole = Window(user), 0
    for ground, _ in planned['grounds']:
        todo = [group for group in planned['groups'] if group['ground'] == ground and not (out / f'{group["number"]}.mod').is_file()]
        if not todo:
            continue
        name = area_name(planned, ground)
        window.open_area(name, f'{name[3:]} {ground}')
        tree, items = window.palette()  # read once for an area: every label is several calls into the Toolset
        for group in todo:
            no_client()
            require(not window.others(), f'A window is up in the Toolset: {window.others()}')
            require(group['name'] in items, 'The palette does not list ' + group['name'])
            try:
                if not window.arm(tree, items[group['name']]):
                    print(group['number'], group['name'], 'NOT ARMED', flush=True)
                    unwhole += 1
                    continue
                require(window.clicked(), 'No click came')
                time.sleep(0.9)
                window.disarm()
                done = window.save(module)
            finally:
                window.undo()  # however the group is left: a click while it was armed may have painted it
            require(not window.others(), f'A window is up in the Toolset: {window.others()}')
            wrong = keep(planned, group, module, out) if done else ['not saved']
            unwhole += bool(wrong)
            print(group['number'], group['name'], '; '.join(wrong) or 'whole', flush=True)
    return unwhole


def main(arguments=None):
    parser = argparse.ArgumentParser(prog='tools.envkit.toolset_paint')
    commands = parser.add_subparsers(dest='command', required=True)
    one = commands.add_parser('prepare')
    one.add_argument('--tileset', required=True)
    one.add_argument('--user', required=True)
    one.add_argument('--haks', nargs='*', default=[], help='packs listed before the usual ones, after the tileset\'s own')
    one.add_argument('--repo', default='.')
    one.add_argument('--game')
    one.add_argument('--only', help='group numbers, comma separated')
    for name in ('run', 'read'):
        commands.add_parser(name).add_argument('--user', required=True)
    chosen = parser.parse_args(arguments)
    if chosen.command == 'prepare':
        only = {int(part) for part in chosen.only.split(',') if part.strip()} if chosen.only else None
        print(json.dumps(prepare(chosen.repo, chosen.tileset, chosen.user, (*chosen.haks, *toolset.HAKS), game=chosen.game, only=only)))
        return 0
    if chosen.command == 'run':
        return int(run(chosen.user) > 0)
    told = read(chosen.user)
    print(json.dumps(told, indent=1))
    return int(any(one['wrong'] for one in told))


if __name__ == '__main__':
    sys.exit(main())
