"""Calibrate, geometry and appearance for one head on a local ComfyUI, with graphs from headkit.comfy.compile_graph (pixal-single-v1).
Launched by `run_headbatch.py gpu`, which names the prepare attempt's matte for calibrate. Every run keeps its own folder under HEAD/gpu."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headkit.comfy import compile_graph  # noqa: E402
from headkit.common import sha, write  # noqa: E402

GEOMETRY_NODE = '961:'
FIELD_NODE = '962:'
SHAPE_NODE = '963:'
GEOMETRY_CAP = 5
COUNTER = re.compile(r'_(\d+)_?\.glb$')
POLL_SECONDS = 3
DEADLINE_SECONDS = 2700  # the deadline of headkit's own ComfyUI routes
OOM_RESEED = 1000
REUSABLE_STAGES = ('calibrate', 'geometry')


class ComfyError(OSError):
    pass


class Comfy:
    deadline = DEADLINE_SECONDS

    def __init__(self, url, root):
        self.url = url.rstrip('/')
        self.root = root

    def send(self, route, data=None):
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.url+route, data=body, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:  # a refused graph gives its reason in the body
            raise ComfyError(f'{route}: HTTP {error.code}: {error.read().decode(errors="replace")[:3000]}') from error

    def call(self, route, data=None):
        return json.loads(self.send(route, data))

    def wait(self, prompt):
        """A failed poll says nothing about the prompt, which is still on the card: keep asking until the deadline."""
        ends = time.time()+self.deadline
        while time.time() < ends:
            try:
                history = self.call('/history/'+prompt)
            except (OSError, ValueError) as error:
                print('poll failed:', error, flush=True)
                history = {}
            status = history.get(prompt, {}).get('status', {})
            if status.get('completed') is not None or status.get('status_str') == 'error':
                return history[prompt]
            time.sleep(POLL_SECONDS)
        raise SystemExit(f'prompt {prompt} did not finish in {self.deadline} s and may still be on the card: check ComfyUI before the next GPU job')

    def free(self):
        self.send('/free', {'unload_models': True, 'free_memory': True})

    def submit(self, graph, before_prompt=lambda: None):
        # Free cached models first (applied between prompts): the card is shared with the desktop, so a decode can run out on cache alone.
        self.free()
        before_prompt()  # after /free: a server that cannot be reached has received no submission
        reply = self.call('/prompt', {'prompt': graph})
        if reply.get('node_errors'):
            raise SystemExit('ComfyUI refused nodes: '+json.dumps(reply['node_errors'])[:3000])
        print('prompt', reply['prompt_id'], flush=True)
        return self.wait(reply['prompt_id'])

    def run(self, graph, out, before_submit=lambda: None):
        started = time.time()
        entry = self.submit(graph, before_submit)
        if failed(entry) and 'out of memory' in json.dumps(entry['status']):
            print(out.name, 'CUDA OOM: freeing VRAM and retrying once', flush=True)
            time.sleep(10)
            entry = self.submit(graph, before_submit)
        seconds = round(time.time()-started, 1)
        out = fresh_folder(out)
        out.mkdir(parents=True)
        (out/'prompt.json').write_text(json.dumps(graph, indent=1))
        (out/'history.json').write_text(json.dumps(entry, indent=1))
        if failed(entry):
            raise SystemExit(f'{out.name} failed: '+json.dumps(entry['status'])[:3000])
        files = {}
        for node, data in entry['outputs'].items():
            for kind in ('images', 'files', '3d'):
                for item in data.get(kind, []):
                    source = self.root/'output'/item.get('subfolder', '')/item['filename']
                    target = out/f"node-{node}-{item['filename']}"
                    link_or_copy(source, target)
                    files[f"{node}:{item['filename']}"] = {'path': str(target), 'sha256': sha(target)}
        if not files:
            raise SystemExit(f'{out.name} finished with no output files')
        return entry, files, seconds


def fresh_folder(folder):
    """ComfyUI can reuse a file name (its counter follows what is left in its output folder), and an earlier run's files are evidence, so no run lands on another."""
    found, number = folder, 1
    while found.exists():
        number += 1
        found = folder.with_name(f'{folder.name}-{number:02d}')
    return found


def failed(entry):
    return entry.get('status', {}).get('status_str') == 'error'


def link_or_copy(source, target):
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)  # ComfyUI output on another drive


def shift_seeds(graph, offset):
    for node in graph.values():
        if 'seed' in node.get('inputs', {}):
            node['inputs']['seed'] += offset


def file_from(files, node):
    return next(value for key, value in files.items() if key.startswith(node))


def calibrate(comfy, head, gpu, ledger, stage_input, prefix, matte):
    from PIL import Image
    ledger['matteAttempt'] = matte.parents[1].name
    rgba = Image.open(matte).convert('RGBA')
    flat = Image.new('RGBA', rgba.size, (0, 0, 0, 255))
    flat.alpha_composite(rgba)
    flat.convert('RGB').save(stage_input/'design.png')
    rgba.save(stage_input/'mask.png')
    design = f'headkit/{head.name}/design.png'
    graph = compile_graph('calibrate', 'pixal-single-v1', {'geometry': design, 'detail': design, 'mask': f'headkit/{head.name}/mask.png'}, prefix)
    entry, files, seconds = comfy.run(graph, gpu/'calibrate')
    fov = {'detail': float(entry['outputs']['10']['text'][0]), 'geometry': float(entry['outputs']['16']['text'][0])}
    shutil.copy2(file_from(files, '13:')['path'], stage_input/'normalized.png')
    return {'seconds': seconds, 'fov': fov, 'files': files}


def save_ledger(gpu, ledger):
    write(gpu/'gpu.json', ledger)


def submissions(gpu, ledger):
    """Older ledgers have no counter, but ComfyUI numbers a head's geometry outputs, so the highest number is a floor for what ran."""
    numbers = [int(found[1]) for path in gpu.glob(f'geometry*/node-{GEOMETRY_NODE[:-1]}-*.glb') if (found := COUNTER.search(path.name))]
    return max([ledger.get('geometrySubmissions', 0), *numbers])


def spend_geometry_submission(head, gpu, ledger):
    """User rule: every submission counts towards the cap, retries and reseeds included, and is on disk before it runs."""
    count = submissions(gpu, ledger)
    if count >= GEOMETRY_CAP and not (head/'geometry-cap-override').exists():
        raise SystemExit(f'{head.name}: {count} geometry submissions reached the cap of {GEOMETRY_CAP}: stop and ask the user')
    ledger['geometrySubmissions'] = count+1
    save_ledger(gpu, ledger)


def geometry(comfy, head, gpu, ledger, prefix, offset):
    fov = ledger['stages']['calibrate']['fov']['detail']
    graph = compile_graph('geometry', 'pixal-single-v1', {'geometry': f'headkit/{head.name}/normalized.png'}, prefix, fov=fov)
    shift_seeds(graph, offset)
    spend = lambda: spend_geometry_submission(head, gpu, ledger)
    try:
        entry, files, seconds = comfy.run(graph, gpu/'geometry', spend)
    except SystemExit as error:
        if 'out of memory' not in str(error):
            raise
        print(head.name, 'geometry OOM after a freed retry: reseeding', flush=True)
        offset += OOM_RESEED
        shift_seeds(graph, OOM_RESEED)
        entry, files, seconds = comfy.run(graph, gpu/f'geometry-oom-r{offset}', spend)
    return {'seconds': seconds, 'fov': fov, 'files': files, 'seedOffset': offset}


def accept_geometry(ledger, row, verdict):
    """An appearance field belongs to one saved shape, and the manifest approves whichever pair the ledger names, so only a shape that passed replaces the pair (RUNBOOK 191)."""
    row['occiput'] = {key: value for key, value in verdict.items() if key != 'bandSquareCm'}
    if verdict['open']:
        ledger.setdefault('rejectedGeometry', []).append(row)
        return False
    ledger['stages'].pop('appearance', None)
    ledger['stages']['geometry'] = row
    return True


def appearance(comfy, head, gpu, ledger, prefix, offset):
    fov = ledger['stages']['calibrate']['fov']['detail']
    if ledger['stages']['geometry'].get('occiput', {}).get('open'):
        raise SystemExit(f'{head.name}: the saved geometry has an open occiput: reseed before appearance')
    shape = file_from(ledger['stages']['geometry']['files'], SHAPE_NODE)
    suffix = f'-r{offset}' if offset else ''
    graph = compile_graph('appearance', 'pixal-single-v1', {'detail': f'headkit/{head.name}/normalized.png'}, prefix+suffix, fov=fov, shape=shape)
    shift_seeds(graph, offset)
    if offset and 'appearance' in ledger['stages']:
        earlier = ledger['stages']['appearance']
        ledger['stages'][f"appearance-seed{earlier.get('seedOffset', 0)}"] = earlier
    entry, files, seconds = comfy.run(graph, gpu/f'appearance{suffix}')
    return {'seconds': seconds, 'fov': fov, 'files': files, 'seedOffset': offset}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('head', type=Path)
    parser.add_argument('--comfy-url', required=True)
    parser.add_argument('--comfy-root', required=True, type=Path)
    parser.add_argument('--stages', default='calibrate,geometry,appearance')
    parser.add_argument('--seed-offset', type=int, default=0)
    parser.add_argument('--upstream', type=Path, help='frozen ledger holding the earlier stages this run reuses')
    parser.add_argument('--matte', type=Path, help="the prepare attempt's design-rgba.png, for calibrate")
    args = parser.parse_args()
    head = args.head.resolve()
    gpu = head/'gpu'
    comfy = Comfy(args.comfy_url, args.comfy_root)
    ledger_path = gpu/'gpu.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'head': head.name, 'stages': {}}
    if args.upstream:
        frozen = json.loads(args.upstream.read_text())['stages']
        ledger['stages'].update({stage: frozen[stage] for stage in REUSABLE_STAGES if stage in frozen and stage not in args.stages.split(',')})
    stage_input = args.comfy_root/'input'/'headkit'/head.name
    stage_input.mkdir(parents=True, exist_ok=True)

    def save():
        save_ledger(gpu, ledger)

    for stage in args.stages.split(','):
        prefix = f'headkit/{head.name}/{stage}'
        if stage == 'calibrate':
            ledger['stages'][stage] = calibrate(comfy, head, gpu, ledger, stage_input, prefix, args.matte)
        elif stage == 'geometry':
            try:
                row = geometry(comfy, head, gpu, ledger, prefix, args.seed_offset)
            finally:
                save()  # a failed submission still counts towards the cap
            # An open back of skull found only after a long CPU chain wastes the whole head, so check the raw shape now.
            from headkit.occiput import back_coverage
            verdict = back_coverage(file_from(row['files'], GEOMETRY_NODE)['path'])
            if not accept_geometry(ledger, row, verdict):
                save()
                raise SystemExit(f"{head.name} GEOMETRY OPEN OCCIPUT (low bands {verdict['lowBands']}): reseed before appearance")
        elif stage == 'appearance':
            ledger['stages'][stage] = appearance(comfy, head, gpu, ledger, prefix, args.seed_offset)
        else:
            raise SystemExit(f'Unknown GPU stage {stage}')
        save()
        print(head.name, stage, ledger['stages'][stage]['seconds'], 's', flush=True)


if __name__ == '__main__':
    main()
