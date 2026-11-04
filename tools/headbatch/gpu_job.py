"""Calibrate, geometry and appearance for one head on a local ComfyUI, with graphs from headkit.comfy.compile_graph (pixal-single-v1).
Launched by `run_headbatch.py gpu`. HEAD/run/prepare must hold the reviewed matte (images/design-rgba.png)."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headkit.comfy import compile_graph  # noqa: E402
from headkit.common import sha  # noqa: E402

GEOMETRY_NODE = '961:'
FIELD_NODE = '962:'
SHAPE_NODE = '963:'
GEOMETRY_CAP = 5
POLL_SECONDS = 3
OOM_RESEED = 1000
REUSABLE_STAGES = ('calibrate', 'geometry')


class Comfy:
    def __init__(self, url, root):
        self.url = url
        self.root = root

    def call(self, route, data=None):
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.url+route, data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)

    def submit(self, graph):
        # Free cached models first (applied between prompts): the card is shared with the desktop, so a decode can run out on cache alone.
        request = urllib.request.Request(self.url+'/free', data=b'{"unload_models": true, "free_memory": true}', headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(request, timeout=120).read()
        prompt = self.call('/prompt', {'prompt': graph})['prompt_id']
        while True:
            history = self.call('/history/'+prompt)
            status = history.get(prompt, {}).get('status', {})
            if status.get('completed') is not None or status.get('status_str') == 'error':
                return history[prompt]
            time.sleep(POLL_SECONDS)

    def run(self, graph, out, before_submit=lambda: None):
        started = time.time()
        before_submit()
        entry = self.submit(graph)
        if failed(entry) and 'out of memory' in json.dumps(entry['status']):
            print(out.name, 'CUDA OOM: freeing VRAM and retrying once', flush=True)
            time.sleep(10)
            before_submit()
            entry = self.submit(graph)
        seconds = round(time.time()-started, 1)
        out.mkdir(parents=True, exist_ok=True)
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
                    if not target.exists():
                        link_or_copy(source, target)
                    files[f"{node}:{item['filename']}"] = {'path': str(target), 'sha256': sha(target)}
        return entry, files, seconds


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


def calibrate(comfy, head, gpu, ledger, stage_input, prefix):
    from PIL import Image
    attempt = sorted((head/'run'/'prepare').glob('attempt-*'))[-1]
    ledger['matteAttempt'] = attempt.name
    rgba = Image.open(attempt/'images'/'design-rgba.png').convert('RGBA')
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
    gpu.mkdir(parents=True, exist_ok=True)
    (gpu/'gpu.json').write_text(json.dumps(ledger, indent=1))


def spend_geometry_submission(head, gpu, ledger):
    """User rule: every submission counts towards the cap, retries and reseeds included, and is on disk before it runs."""
    count = ledger.get('geometrySubmissions', 0)
    if count >= GEOMETRY_CAP and not (head/'geometry-cap-override').exists():
        raise SystemExit(f'{head.name}: {count} geometry submissions reached the cap of {GEOMETRY_CAP}: stop and ask the user')
    ledger['geometrySubmissions'] = count+1
    save_ledger(gpu, ledger)


def geometry(comfy, head, gpu, ledger, prefix, offset):
    fov = ledger['stages']['calibrate']['fov']['detail']
    graph = compile_graph('geometry', 'pixal-single-v1', {'geometry': f'headkit/{head.name}/normalized.png'}, prefix, fov=fov)
    shift_seeds(graph, offset)
    spend = lambda: spend_geometry_submission(head, gpu, ledger)
    # An appearance field belongs to one saved shape, and the manifest approves whichever pair the ledger names.
    ledger['stages'].pop('appearance', None)
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


def appearance(comfy, head, gpu, ledger, prefix, offset):
    fov = ledger['stages']['calibrate']['fov']['detail']
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
            ledger['stages'][stage] = calibrate(comfy, head, gpu, ledger, stage_input, prefix)
        elif stage == 'geometry':
            try:
                ledger['stages'][stage] = geometry(comfy, head, gpu, ledger, prefix, args.seed_offset)
            finally:
                save()  # a failed submission still counts towards the cap
            # An open back of skull found only after a long CPU chain wastes the whole head, so check the raw shape now.
            from headkit.occiput import back_coverage
            verdict = back_coverage(file_from(ledger['stages'][stage]['files'], GEOMETRY_NODE)['path'])
            ledger['stages'][stage]['occiput'] = {key: value for key, value in verdict.items() if key != 'bandSquareCm'}
            if verdict['open']:
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
