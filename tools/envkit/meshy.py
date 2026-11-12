"""Meshy generation under a credit cap, through the pinned meshy-cli (which owns the credentials).

Two routes. A prop is generated in smart-topology mode, which builds low-poly parts to a triangle target. A building is
generated in full detail from up to four views and then remeshed inside Meshy to a target. Only a model whose triangle
count was bounded that way becomes a working model (user rule, 2026-11-10: lean on Meshy's remesh, nothing over 100k
into the pipeline unless it has to; raised to 200k for larger buildings, 2026-11-11). The full-detail result, which runs to millions of triangles, can be fetched only
as a master: a spare kept apart from the working model.

Every paid call is reserved in the ledger before it is sent, so a crash between sending and recording leaves the credits
counted, not lost track of. Every change to the ledger is made under a lock shared by all processes, so two calls at
once cannot both pass the cap or drop each other's entry."""
import contextlib
import datetime
import json
import math
import re
import shutil
import struct
import subprocess
import time
from pathlib import Path

from . import require

CLI = ('npm', 'exec', '--yes', '--package=meshy-cli@0.4.0', '--', 'meshy')
PRICES = {'prop': 15, 'building': 30, 'remesh': 5}  # docs.meshy.ai/en/api/pricing, read 2026-11-10
RESOURCE = {'prop': 'image-to-3d', 'building': 'multi-image-to-3d', 'remesh': 'remesh'}
BOUNDED = {'prop', 'remesh'}  # the operations whose result has a triangle target
MAX_TRIANGLES = 100000
BUILDING_TRIANGLES = 200000  # a remeshed building (user, 2026-11-11: "raise our poly budget for larger buildings to 200k")
PROP_TRIANGLES = (100, 15000)  # smart-topology's own range
REMESH_HEADROOM = 0.92  # a remesh lands a little over its target: the robe trial asked for 100,000 and got 103,196
KEY = re.compile(r'[a-z0-9][a-z0-9-]{0,79}')
# Answers that mean the task was not created: no credential, no credits, not allowed, queue full. The Ares Depot run
# (2026-11-11) hit the plan's ten queued tasks; the eleventh came back 429 and had been left counted as uncertain.
REFUSED = (401, 402, 403, 429)
QUEUE = 10  # the tasks Meshy holds for this plan at once: the next is refused, and the CLI never sends a refused key again
IMAGES = ('.png', '.jpg', '.jpeg', '.webp')


class Ledger:
    """One JSON file: the cap and every paid call, counted at its estimate until Meshy reports what it consumed."""

    PATIENCE = 30.0  # seconds to wait for another call's change; a change takes milliseconds

    def __init__(self, path):
        self.path = Path(path); self.load()

    def load(self):
        """Read the file again, between other calls' changes: on Windows a file being read cannot be replaced, nor one
        being replaced read."""
        with self.changing():
            pass

    def changing(self):
        """Hold the ledger for one change (read, check, write) against every other process and thread, and read it
        afresh: a wait holds a ledger object for minutes while other calls add entries, so every change starts from
        the file as it is now. Used as `with ledger.changing():`; a change ends with `save`."""
        from tools.headkit.gpu_lock import locked
        held = contextlib.ExitStack(); deadline = time.monotonic() + self.PATIENCE
        while True:
            try:
                held.enter_context(locked(self.path)); break
            except FileExistsError:
                require(time.monotonic() < deadline, 'The ledger is held by another call: ' + str(self.path))
                time.sleep(0.02)
        try:
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            require(self.data.get('kind') == 'srn-envkit-meshy-ledger', 'Envkit Meshy ledger required')
        except BaseException:
            held.close(); raise
        return held

    @classmethod
    def create(cls, path, cap):
        path = Path(path)
        require(type(cap) is int and cap > 0, 'Credit cap must be a positive whole number')
        require(not path.exists(), 'Ledger already exists: ' + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'schemaVersion': 1, 'kind': 'srn-envkit-meshy-ledger', 'cap': cap, 'entries': []}, indent=1),
                        encoding='utf-8')
        return cls(path)

    def save(self):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.data, indent=1), encoding='utf-8'); temporary.replace(self.path)

    def entry(self, key):
        found = [row for row in self.data['entries'] if row['key'] == key]
        require(found, 'No ledger entry: ' + str(key))
        return found[0]

    def committed(self):
        return sum(row['estimate'] if row.get('credits') is None else row['credits'] for row in self.data['entries'])

    def reserve(self, key, asset, operation, arguments):
        require(isinstance(key, str) and KEY.fullmatch(key) is not None, 'Ledger keys must be safe IDs: ' + str(key))
        with self.changing():
            require(all(row['key'] != key for row in self.data['entries']), 'Key already used: ' + key)
            estimate = PRICES[operation]
            require(self.committed() + estimate <= self.data['cap'],
                    f'Credit cap would be exceeded: {self.committed()} committed + {estimate} > {self.data["cap"]}')
            row = {'key': key, 'asset': asset, 'operation': operation, 'estimate': estimate, 'state': 'reserved', 'taskId': None,
                   'credits': None, 'arguments': arguments}
            self.data['entries'].append(row); self.save()
        return row

    def raise_cap(self, cap, reason, *, today=None):
        """Raise the cap, keeping what it was, when it changed and why: the cap is the spending the user has approved,
        so a raise states their approval. It is never lowered here, nor raised without a reason."""
        require(type(cap) is int and isinstance(reason, str) and reason.strip(), 'A raise states the new cap and the approval it rests on')
        with self.changing():
            require(cap > self.data['cap'], f'The cap is {self.data["cap"]} already: a raise goes above it')
            self.data.setdefault('raises', []).append({'from': self.data['cap'], 'to': cap, 'reason': reason.strip(),
                                                       'date': today or datetime.date.today().isoformat()})
            self.data['cap'] = cap; self.save()

    def update(self, key, **fields):
        with self.changing():
            self.entry(key).update(fields); self.save()

    def release(self, key):
        """Drop a reservation whose call was never sent: its credits and its key are free again."""
        with self.changing():
            row = self.entry(key)
            require(row['state'] == 'reserved', 'Only an unsent reservation is released: ' + key)
            self.data['entries'].remove(row); self.save()


class NotSent(ValueError):
    """The call was refused before anything reached Meshy."""


def _images(paths):
    paths = [Path(path).resolve() for path in paths]
    require(paths and all(path.is_file() and path.suffix.lower() in IMAGES for path in paths), 'Reference images required')
    return [str(path) for path in paths]


def prop_arguments(image, triangles, resolution='2k'):
    require(type(triangles) is int and PROP_TRIANGLES[0] <= triangles <= PROP_TRIANGLES[1],
            f'A prop target is {PROP_TRIANGLES[0]}-{PROP_TRIANGLES[1]} triangles')
    return ['--image-url', _images([image])[0], '--model-type', 'smart-topology', '--target-polycount', str(triangles),
            '--should-texture', 'true', '--enable-pbr', 'true', '--texture-resolution', resolution, '--target-formats', 'glb']


def building_arguments(images, resolution='4k'):
    require(1 <= len(images) <= 4, 'A building takes one to four views')
    return ['--image-urls', ','.join(_images(images)), '--should-texture', 'true', '--enable-pbr', 'true',
            '--texture-resolution', resolution, '--target-formats', 'glb']


def remesh_arguments(task, triangles):
    """`triangles` is the ceiling wanted; the request asks for a little less because a remesh overshoots."""
    require(type(triangles) is int and 100 <= triangles <= BUILDING_TRIANGLES, f'A remesh ceiling is 100-{BUILDING_TRIANGLES} triangles')
    require(isinstance(task, str) and task, 'Remesh the generation task by its id')
    return ['--input-task-id', task, '--topology', 'triangle', '--target-polycount', str(int(triangles * REMESH_HEADROOM)),
            '--target-formats', 'glb']


def run_cli(arguments, folder):
    """(exit code, parsed stdout). The launcher is an npm .cmd shim, which cmd.exe re-parses: text it would rewrite is refused."""
    if any(set('\r\n"%&|<>^') & set(value) for value in arguments):
        raise NotSent('Meshy arguments cannot contain line breaks or the characters " % & | < > ^')
    executable = shutil.which(CLI[0])
    if executable is None:
        raise NotSent('npm not found')
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    full = [executable, *CLI[1:], *arguments, '--output-schema', 'v1', '--format', 'json', '--no-update-check']
    result = subprocess.run(full, capture_output=True, text=True, encoding='utf-8', check=False)
    (folder / 'stdout.json').write_text(result.stdout, encoding='utf-8'); (folder / 'stderr.log').write_text(result.stderr, encoding='utf-8')
    text = result.stdout.strip()
    return result.returncode, (json.loads(text[text.index('{'):]) if '{' in text else {})


def task_fields(response):
    result = response.get('result', response)
    if not isinstance(result, dict):
        result = {'id': result} if isinstance(result, str) else {}
    task = result.get('task') or result.get('submission') or result
    return {'id': task.get('task_id') or task.get('id') or result.get('task_id'), 'status': task.get('status'),
            'credits': task.get('consumed_credits')}


def submit(ledger, key, asset, operation, arguments, folder, *, run=run_cli):
    """Reserve, then send once. An answer without a task id leaves the entry `uncertain` and still counted; a call
    refused before it was sent gives its reservation back."""
    require(operation in PRICES, 'Unknown operation: ' + str(operation))
    folder = Path(folder)  # a missing folder is refused here, before anything is reserved
    ledger.reserve(key, asset, operation, arguments)
    try:
        code, response = run([RESOURCE[operation], 'create', '--async', '--operation-id', key, '--include-raw', *arguments],
                             folder / key / 'create')
    except NotSent:
        ledger.release(key); raise
    error = response.get('error') if isinstance(response.get('error'), dict) else {}
    result = response.get('result') if isinstance(response.get('result'), dict) else {}
    rejected = (result.get('submission') or {}).get('state') == 'rejected'  # the CLI remembers a refused operation id
    if code != 0 and (error.get('http_status') in REFUSED or rejected):  # the answer was no: nothing was created
        ledger.release(key)
        raise ValueError(f'Meshy refused {key}' + ('; the CLI will not send this key again, so use a new one' if rejected else '')
                         + f': {error.get("message")}')
    task = task_fields(response)['id'] if code == 0 else None
    ledger.update(key, state='submitted' if task else 'uncertain', taskId=task)
    require(task, 'Submission uncertain; check the Meshy task list before any retry of ' + key)
    return task


def wait(ledger, key, folder, *, timeout=1800, run=run_cli):
    row = ledger.entry(key)
    require(row['taskId'] and row['state'] in ('submitted', 'pending', 'in_progress'), 'Nothing to wait for: ' + key)
    saved = Path(folder) / key / 'task.json'
    if saved.exists():
        saved.unlink()  # the CLI never overwrites, and an earlier wait may have timed out with the task unfinished
    code, response = run([RESOURCE[row['operation']], 'wait', row['taskId'], '--timeout', str(timeout), '--include-raw',
                          '--save-json', str(saved)], Path(folder) / key / 'wait')
    fields = task_fields(response)
    if fields['status'] in ('SUCCEEDED', 'FAILED', 'CANCELED'):
        ledger.update(key, state=fields['status'].lower(), credits=fields['credits'], task=str(saved))
    require(code == 0 and fields['status'] == 'SUCCEEDED', f'Task {key} is {fields["status"]}')
    return fields


def triangles(glb):
    """Triangles in a binary glTF, from the index counts of its triangle primitives."""
    data = Path(glb).read_bytes()
    require(data[:4] == b'glTF', 'Binary glTF required: ' + str(glb))
    length, kind = struct.unpack_from('<II', data, 12)
    require(kind == 0x4E4F534A, 'glTF JSON chunk missing')
    document = json.loads(data[20:20 + length]); total = 0
    for mesh in document.get('meshes', []):
        for primitive in mesh['primitives']:
            require(primitive.get('mode', 4) == 4, 'Only triangle lists are counted')
            accessor = primitive['indices'] if 'indices' in primitive else primitive['attributes']['POSITION']
            total += document['accessors'][accessor]['count'] // 3
    return total


def _ceiling(row):
    """The most triangles a working model of this ledger entry has. A remesh is held to the ceiling it was asked for
    where that is over the common one: only a remesh sent for a larger building's budget may come back that large."""
    sent = row.get('arguments') or []
    if row['operation'] != 'remesh' or '--target-polycount' not in sent[:-1]:
        return MAX_TRIANGLES
    asked = math.ceil(int(sent[sent.index('--target-polycount') + 1]) / REMESH_HEADROOM - 1e-9)  # the least ceiling that sends this target
    return max(MAX_TRIANGLES, min(BUILDING_TRIANGLES, asked))


def download(ledger, key, folder, bank, *, master=False, run=run_cli):
    """Fetch a finished model. A working model comes from a bounded operation and must be at or under the ceiling.

    `master` fetches a full-detail generation instead, as a spare kept beside the working model while the kit is still
    learning how the reduced models hold up (user, 2026-11-10). A master has no ceiling and is never the game model."""
    row = ledger.entry(key)
    if master:
        require(row['operation'] not in BOUNDED, key + ' is already a reduced model; download it without master')
    else:
        require(row['operation'] in BOUNDED, 'Only a remeshed or smart-topology model is a working model; remesh ' + key
                + ' first, or fetch it as a master')
    require(row['state'] == 'succeeded' and row.get('task'), 'Successful task required: ' + key)
    bank = Path(bank)
    require(not bank.exists(), 'Fresh download folder required: ' + str(bank))
    code, _ = run(['download', '--task-json', row['task'], '--all', '--output-dir', str(bank.resolve())], Path(folder) / key / 'download')
    models = sorted(bank.rglob('*.glb')) if bank.exists() else []
    if code != 0 or not models:
        shutil.rmtree(bank, ignore_errors=True)  # what came down is no model, and would stand in the way of the retry
        raise ValueError('Download incomplete: ' + key)
    counts = {str(path): triangles(path) for path in models}
    ceiling = _ceiling(row); accepted = bool(master) or max(counts.values()) <= ceiling  # the ledger says so, so the folder is not taken for a working model
    ledger.update(key, downloaded=str(bank), triangles=counts, master=bool(master), accepted=accepted)
    require(accepted, f'Model exceeds {ceiling} triangles and is not a working model: {counts}')
    return counts
