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
import uuid
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headkit.comfy import compile_graph  # noqa: E402
from headkit.common import sha, write, pin, verify  # noqa: E402
from resource_budget import Budget, Watchdog
import gpu_contract

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
        self.budget = None
        self.unresolved = None

    def send(self, route, data=None, *, timeout=5):
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.url+route, data=body, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:  # a refused graph gives its reason in the body
            raise ComfyError(f'{route}: HTTP {error.code}: {error.read().decode(errors="replace")[:3000]}') from error

    def call(self, route, data=None, *, timeout=5):
        return json.loads(self.send(route, data, timeout=timeout))

    def queue(self,timeout=5):
        queue=self.call('/queue',timeout=timeout)
        if (not isinstance(queue,dict) or any(not isinstance(queue.get(key),list) for key in ('queue_running','queue_pending'))
                or any(not isinstance(row,list) or len(row)<2 or not isinstance(row[1],str) or not row[1]
                       for key in ('queue_running','queue_pending') for row in queue[key])):
            raise ComfyError('Malformed shared GPU queue; ownership/idle state is unknown')
        return queue

    def interrupt_owned(self,prompt):
        queue=self.queue(timeout=2)
        running=queue['queue_running']
        # /interrupt is global on older Comfy versions. Never interrupt an unrelated running job.
        if not running or any(row[1]!=prompt for row in running):return False
        self.send('/interrupt',{'prompt_id':prompt},timeout=2)
        return True

    def wait(self, prompt):
        """A bounded polling loop plus an independent owned-prompt watchdog."""
        ends=time.monotonic()+self.deadline
        with Watchdog(self.budget,lambda:self.interrupt_owned(prompt)) as monitor:
            while time.monotonic()<ends:
                try:history=self.call('/history/'+prompt)
                except (OSError,ValueError) as error:
                    print('poll failed:',error,flush=True);history={}
                status=history.get(prompt,{}).get('status',{})
                if status.get('completed') is not None or status.get('status_str')=='error':
                    monitor.check()
                    if self.unresolved:self.unresolved.unlink(missing_ok=True)
                    if monitor.reason:
                        raise SystemExit('Resource supervision stopped owned prompt '+prompt+': '+monitor.reason)
                    return history[prompt]
                time.sleep(POLL_SECONDS)
        raise SystemExit(f'prompt {prompt} did not finish in {self.deadline} s; reconcile before the next GPU job')

    def ensure_idle(self):
        queue=self.queue()
        if queue['queue_running'] or queue['queue_pending']:
            raise ComfyError('Shared GPU queue is busy; leave its jobs and resident models untouched')
    def free(self):
        self.ensure_idle()
        self.send('/free', {'unload_models': True, 'free_memory': True})

    def submit(self, graph, before_prompt=lambda: None):
        # Free cached models first (applied between prompts): the card is shared with the desktop, so a decode can run out on cache alone.
        if self.budget:self.budget.check()
        self.free()
        before_prompt()  # after /free: a server that cannot be reached has received no submission
        token=uuid.uuid4().hex
        if self.unresolved:write(self.unresolved,{'state':'submitting; reconcile by clientId','clientId':token,'graph':graph})
        reply = self.call('/prompt', {'prompt': graph,'client_id':token})
        if not isinstance(reply,dict) or not isinstance(reply.get('prompt_id'),str) or not reply['prompt_id']:
            raise ComfyError('Prompt reply has no usable ID; preserve clientId and reconcile before resuming')
        if self.unresolved:
            write(self.unresolved, {'state':'running','promptId':reply['prompt_id'],'clientId':token})
        if reply.get('node_errors'):
            raise SystemExit('ComfyUI refused nodes: '+json.dumps(reply['node_errors'])[:3000])
        print('prompt', reply['prompt_id'], flush=True)
        return self.wait(reply['prompt_id'])

    def run(self, graph, out, before_submit=lambda: None):
        started = time.time()
        requested = out
        for retry in range(2):
            out = fresh_folder(requested)
            out.mkdir(parents=True)
            write(out/'prompt.json', graph)
            try:
                entry = self.submit(graph, before_submit)
            except BaseException as error:
                write(out/'failure.json', {'type':type(error).__name__,'error':str(error),'elapsedSeconds':time.time()-started})
                raise
            write(out/'history.json', entry)
            if retry == 0 and failed(entry) and 'out of memory' in json.dumps(entry['status']):
                print(out.name, 'CUDA OOM: evidence saved; freeing VRAM and retrying once', flush=True)
                time.sleep(10)
            else:
                break
        seconds = round(time.time()-started, 1)
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


def calibrate(comfy, head, gpu, ledger, stage_input, prefix, matte=None, prepared=None):
    from PIL import Image
    sources = json.loads(Path(prepared).read_text()) if prepared else None
    if sources:
        verify(sources['pins']+[sources['receipt'], *sources['images'].values()], fresh=True)
        ledger['matteAttempt'] = sources['attempt']
        images = {role:Path(row['path']) for role,row in sources['images'].items()}
    else:
        ledger['matteAttempt'] = matte.parents[1].name
        images = {'geometry':matte,'detail':matte,'mask':matte}
    for role, source in images.items():
        with Image.open(source) as image:rgba=image.convert('RGBA')
        if role == 'mask':
            rgba.save(stage_input/'mask.png')
        else:
            flat=Image.new('RGBA',rgba.size,(0,0,0,255));flat.alpha_composite(rgba)
            flat.convert('RGB').save(stage_input/f'{role}.png')
    inputs={role:f'headkit/{head.name}/{role}.png' for role in images}
    graph=compile_graph('calibrate','pixal-single-v1',inputs,prefix)
    entry,files,seconds=comfy.run(graph,gpu/'calibrate')
    fov={'detail':float(entry['outputs']['10']['text'][0]),'geometry':float(entry['outputs']['16']['text'][0])}
    # Divergent estimates indicate inconsistent conditioning, not permission to pick an arbitrary camera.
    if not all(25<=v<=70 for v in fov.values()) or abs(fov['detail']-fov['geometry'])>8:
        raise SystemExit(f'Calibration FOV requires review before geometry: {fov}')
    normalized={}
    for role,node in (('geometry','12:'),('detail','13:')):
        target=stage_input/f'normalized-{role}.png'
        shutil.copy2(file_from(files,node)['path'],target)
        normalized[role]=pin(target)
    return {'seconds':seconds,'fov':fov,'sharedFov':fov['detail'],'files':files,
            'conditioning':normalized,'mode':'paired' if sources and sources.get('paired') else 'bootstrap',
            'prepared':{'receipt':sources['receipt'],'images':sources['images']} if sources else None}


def conditioning_image(ledger, head, role):
    row=ledger['stages']['calibrate']
    if 'conditioning' not in row:  # historical one-image bootstrap ledgers remain readable
        return f'headkit/{head.name}/normalized.png'
    item=row['conditioning'][role]
    verify([item],fresh=True)
    return f'headkit/{head.name}/'+Path(item['path']).name


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
    graph = compile_graph('geometry', 'pixal-single-v1', {'geometry': conditioning_image(ledger, head, 'geometry')}, prefix, fov=fov)
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
    return {'seconds': seconds, 'fov': fov, 'files': files, 'seedOffset': offset,
            'submission':ledger['geometrySubmissions'],
            'conditioningDigest':gpu_contract.calibration_id(ledger['stages']['calibrate'])}


def accept_geometry(ledger, row, verdict):
    """An appearance field belongs to one saved shape, and the manifest approves whichever pair the ledger names, so only a shape that passed replaces the pair (RUNBOOK 191)."""
    row['occiput'] = {key: value for key, value in verdict.items() if key != 'bandSquareCm'}
    if verdict['open']:
        ledger.setdefault('rejectedGeometry', []).append(row)
        return False
    ledger['stages'].pop('appearance', None)
    ledger.pop('geometryReview',None)
    ledger['stages']['geometry'] = row
    return True


def appearance(comfy, head, gpu, ledger, prefix, offset):
    if ledger['stages']['geometry'].get('occiput', {}).get('open'):
        raise SystemExit(f'{head.name}: the saved geometry has an open occiput: reseed before appearance')
    gpu_contract.require_geometry_review(head,ledger)
    fov = ledger['stages']['calibrate']['fov']['detail']
    shape = file_from(ledger['stages']['geometry']['files'], SHAPE_NODE)
    suffix = f'-r{offset}' if offset else ''
    graph = compile_graph('appearance', 'pixal-single-v1', {'detail': conditioning_image(ledger, head, 'detail')}, prefix+suffix, fov=fov, shape=shape)
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
    parser.add_argument('--prepared', type=Path, help='frozen reviewed paired prepare inputs')
    parser.add_argument('--resources', type=Path, help='frozen workspace memory budget')
    parser.add_argument('--matte', type=Path, help="the prepare attempt's design-rgba.png, for calibrate")
    args = parser.parse_args()
    selected = gpu_contract.stages(args.stages)
    head = args.head.resolve()
    gpu = head/'gpu'
    comfy = Comfy(args.comfy_url, args.comfy_root)
    comfy.unresolved = gpu/'UNRECONCILED'
    if comfy.unresolved.exists():
        raise SystemExit('Unreconciled GPU submission; inspect its prompt ID before resuming')
    if args.resources:
        comfy.budget = Budget(json.loads(args.resources.read_text()), fresh_folder(gpu/'resources')/'summary.json')
    ledger_path = gpu/'gpu.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'head': head.name, 'stages': {}}
    if args.upstream:
        frozen = json.loads(args.upstream.read_text())['stages']
        ledger['stages'].update({stage: frozen[stage] for stage in REUSABLE_STAGES if stage in frozen and stage not in args.stages.split(',')})
    stage_input = args.comfy_root/'input'/'headkit'/head.name
    stage_input.mkdir(parents=True, exist_ok=True)

    def save():
        save_ledger(gpu, ledger)

    try:
        if comfy.budget:comfy.budget.start()
        for stage in selected:
            prefix = f'headkit/{head.name}/{stage}'
            if stage == 'calibrate':
                calibrated = calibrate(comfy, head, gpu, ledger, stage_input, prefix, args.matte, args.prepared)
                # Recalibration replaces mutable normalized files; retain history but invalidate all dependent state.
                ledger.setdefault('superseded',[]).append({'stages':dict(ledger['stages']),'geometryReview':ledger.pop('geometryReview',None)})
                ledger['stages'] = {'calibrate':calibrated}
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
                save()
                print('WAITING ON REVIEW: raw geometry; headbatch will draw the exact-submission sheet in a CPU slot', flush=True)
                if 'appearance' in selected:
                    raise SystemExit(3)
            elif stage == 'appearance':
                ledger['stages'][stage] = appearance(comfy, head, gpu, ledger, prefix, args.seed_offset)
            else:
                raise SystemExit(f'Unknown GPU stage {stage}')
            save()
            print(head.name, stage, ledger['stages'][stage]['seconds'], 's', flush=True)
    finally:
        if comfy.budget:comfy.budget.close()



if __name__ == '__main__':
    main()
