"""Stage, GPU and design launches through the shared-tool launcher, with their locks, guards and timing log."""
from contextlib import ExitStack, contextmanager
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time
import urllib.request

from gpu_job import SHAPE_NODE, file_from
import guards
from head_files import write_json
from headkit.comfy import locked
from workspace import PYTHON, REPO, TOOLS

HEADKIT = TOOLS/'headkit'
RUN_HEADKIT = HEADKIT/'run_headkit.py'
GPU_JOB = Path(__file__).with_name('gpu_job.py')
FINISHED_STAGES = ('export', 'native')  # the spooler or a person takes these on; a render waits for its review (RUNBOOK 63)
LOCK_POLL_SECONDS = 2
# Only what each job imports: a toolkit edit elsewhere must not invalidate a GPU or design launch in flight (RUNBOOK 40).
GPU_MODULES = tuple(f'tools/headkit/{name}.py' for name in ('__init__', 'comfy', 'common', 'gltf', 'occiput', 'source_inventory'))
DESIGN_MODULES = tuple(f'tools/headkit/{name}.py' for name in ('run_headkit', '__init__', '__main__', 'common', 'comfy', 'design', 'source_inventory'))
DEFAULT_GPU_STAGES = 'calibrate,geometry,appearance'


class LaunchFailed(Exception):
    pass


def stamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def timing(workspace, text, started):
    with open(workspace.root/'timings.log', 'a', encoding='utf-8') as log:
        log.write(f"{datetime.now():%H:%M} {text} {int(time.time()-started)} s\n")


@contextmanager
def lock(paths, sleep=time.sleep):
    """Take the first free lock of paths(), asked again on each pass. The system holds it for this process, so a killed launch leaves nothing to clear (RUNBOOK 190)."""
    while True:
        for path in paths():
            held = locked(path)
            try:
                held.__enter__()
            except FileExistsError:
                continue
            try:
                yield path
            finally:
                held.__exit__(None, None, None)
            return
        sleep(LOCK_POLL_SECONDS)


def cpu_slot(workspace):
    """The first free slot of the current limit, which can change while this waits."""
    return lock(lambda: [workspace.locks/f'cpu-{index+1}' for index in range(workspace.cpu_slots())])


def gpu_lock(workspace):
    """One GPU job at a time: designs behind Pixal jobs time out or run out of memory."""
    return lock(lambda: [workspace.locks/'gpu'])


@contextmanager
def head_locks(workspace, names):
    """One launch per head: headkit refuses a second runner on a head outright, which would lose every head of that launch (RUNBOOK 190)."""
    with ExitStack() as stack:
        for name in names:
            try:
                stack.enter_context(guards.head_lock(workspace, name))
            except FileExistsError:
                raise guards.Refused(f'{name}: another launch of this head is queued or running (RUNBOOK 190)') from None
        yield


def launch(workspace, output, inputs, arguments, environment=None):
    """Run one tool through the shared launcher and return its launch record. Invalid launches raise."""
    if output.exists():
        raise LaunchFailed(f'{output} already exists: launch records are never reused')
    command = [PYTHON, '-B', str(TOOLS/'phenotypes/launch_shared_tool.py'), '--toolchain', str(workspace.path(workspace.data['toolchain'])),
               '--migration-receipt', str(workspace.path(workspace.data['migrationReceipt'])), '--tool', 'python', '--output', str(output),
               '--input-path-list', str(inputs), '--', *[str(item) for item in arguments]]
    done = subprocess.run(command, env=environment or workspace.python_environment(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    record = output/'launch.json'
    if not record.exists():
        raise LaunchFailed(f'The launcher wrote no record (exit {done.returncode}): {done.stderr.strip()[-800:]}')
    data = json.loads(record.read_text(encoding='utf-8'))
    if not data['inputsUnchanged'] or data['verificationError']:
        raise LaunchFailed(f"Launch invalid: {data['verificationError'] or 'an input changed during the run'}")
    return data


def run_stages(workspace, name, stages, heads, approve=None, notes=None):
    """Guards, then one launch for all heads (native compiles every eligible head in one Blender run). Returns the per-head stage results."""
    stage_list = stages.split(',')
    dirs = [workspace.head(head) for head in heads]
    bindings = workspace.path(workspace.data['headBindings'])
    landmarks = workspace.landmarks()
    label = f'{stamp()}-{name}'
    folder = workspace.launches
    with head_locks(workspace, heads):
        guards.crlf_in_pinned_code()
        guards.clean_stray_bytecode(bindings)
        for head in dirs:
            guards.loop_budget(head, stage_list, workspace.data.get('loopBudget'))
            if 'repair' in stage_list:
                guards.uv_margin(head)
            if 'ownership' in stage_list:
                guards.ownership_rules(head)
            if approve == 'repair':
                guards.jaw(head, landmarks)
        with cpu_slot(workspace):
            guards.clean_stray_bytecode(bindings)  # strays recur, and the wait for a slot can be long (RUNBOOK 92)
            started = time.time()
            head_list = folder/f'heads-{label}.json'
            input_list = folder/f'inputs-{label}.json'
            write_json(head_list, [{'manifest': str(d/'manifest.json'), 'bindings': str(d/'bindings.json'), 'run': str(d/'run')} for d in dirs])
            wanted = stages+(f',{approve}' if approve else '')
            subprocess.run([PYTHON, '-B', str(RUN_HEADKIT), 'inputs', '--heads', str(head_list), '--output', str(input_list), '--stages', wanted],
                           env=workspace.python_environment(), check=True, stdout=subprocess.DEVNULL)
            batch = [RUN_HEADKIT, 'batch', '--heads', head_list, '--stages', stages, '--precompile', folder/f'precompile-{label}']
            if approve:
                batch += ['--approve', approve, '--notes', notes or '']
            output = folder/f'launch-{label}'
            data = launch(workspace, output, input_list, batch)
            timing(workspace, f'cpu {name} {stages}', started)
    return {'label': label, 'exitCode': data['exitCode'], 'elapsedSeconds': data['elapsedSeconds'], 'heads': results(output/'stdout.log')}


def results(stdout):
    """Stage statuses from run_headkit's batch output; empty when it printed something else, which the spooler reports (RUNBOOK 117)."""
    try:
        parsed = json.loads(Path(stdout).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    rows = parsed.get('heads', parsed) if isinstance(parsed, dict) else parsed
    return [{'id': row.get('id'), 'error': row.get('error', ''), 'stages': [{key: s[key] for key in ('stage', 'status', 'error', 'attempt') if key in s} for s in row.get('stages', [])]}
            for row in rows if isinstance(row, dict)]


def status(workspace):
    """One line per head. A head whose newest stage finished with no launch queued is waiting on review, which is easy to miss (RUNBOOK 63)."""
    lines = []
    if not workspace.heads.is_dir():
        return lines
    for head in sorted(path for path in workspace.heads.iterdir() if (path/'run').is_dir()):
        receipts = sorted(head.glob('run/*/attempt-*/receipt.json'), key=lambda path: path.stat().st_mtime)
        if not receipts:
            lines.append(f'{head.name} | no stage yet')
            continue
        newest = receipts[-1]
        receipt = guards.read(newest)
        state = 'failed' if receipt.get('error') else 'ran'
        stage = newest.parts[-3]
        progress = head/'run'/'state.json'
        reviewed = stage == 'render' and progress.exists() and stage in guards.read(progress).get('reviews', {})
        finished = state == 'ran' and (stage in FINISHED_STAGES or reviewed)
        note = 'launch queued or running' if guards.head_busy(workspace, head.name) else 'finished' if finished else 'WAITING ON REVIEW'
        lines.append(f'{head.name} | {stage} {newest.parts[-2]} {state} | {note}')
    return lines


def reused_gpu_inputs(workspace, head, label, stages):
    """What a partial run takes from earlier stages: a frozen ledger, ComfyUI's normalized image and the saved shape (AGENTS: declare consumed inputs)."""
    if 'calibrate' in stages and ('geometry' in stages or 'appearance' not in stages):
        return [], []
    ledger = head/'gpu'/'gpu.json'
    data = guards.read(ledger) if ledger.exists() else {'stages': {}}
    needed = ['geometry'] if 'appearance' in stages and 'geometry' not in stages else []
    needed += [] if 'calibrate' in stages else ['calibrate']
    missing = [stage for stage in needed if stage not in data['stages']]
    if missing:
        raise guards.Refused(f'{head.name}: {" and ".join(missing)} must run before {",".join(stages)}')
    frozen = head/'launches'/f'gpu-{label}.json'
    write_json(frozen, data)
    files = [str(frozen)]
    if 'calibrate' not in stages:
        files.append(str(workspace.path(workspace.data['comfy']['root'])/'input'/'headkit'/head.name/'normalized.png'))
    if 'geometry' in needed:
        files.append(file_from(data['stages']['geometry']['files'], SHAPE_NODE)['path'])
    return files, ['--upstream', frozen]


def run_gpu(workspace, name, arguments):
    """Calibrate, geometry with its occiput check, and appearance for one head on the workspace's ComfyUI."""
    head = workspace.head(name)
    stages = (arguments[arguments.index('--stages')+1] if '--stages' in arguments else DEFAULT_GPU_STAGES).split(',')
    comfy = workspace.data.get('comfy')
    with head_locks(workspace, [name]):
        if 'geometry' in stages:  # appearance reuses the saved shape and spends no submission
            guards.geometry_cap(head)
        if not comfy:
            raise guards.Refused('This step needs "comfy" in workspace.json')
        with gpu_lock(workspace):
            started = time.time()
            label = f'{stamp()}-gpu'
            matte = guards.attempts(head, 'prepare')[-1]/'images'/'design-rgba.png'
            templates = sorted(str(path) for path in (HEADKIT/'templates').glob('*.json'))
            input_list = head/'launches'/f'inputs-{label}.json'
            reused, upstream = reused_gpu_inputs(workspace, head, label, stages)
            write_json(input_list, [str(REPO/module) for module in GPU_MODULES]+templates+[str(GPU_JOB), str(matte)]+reused)
            job = [GPU_JOB, head, '--comfy-url', comfy['url'], '--comfy-root', workspace.path(comfy['root']), *arguments, *upstream]
            data = launch(workspace, head/'launches'/f'launch-{label}', input_list, job, workspace.python_environment(packages=True))
            timing(workspace, f'gpu {name} {" ".join(arguments)} exit {data["exitCode"]}', started)
    return {**data, 'errors': head/'launches'/f'launch-{label}'/'stderr.log'}


def run_design(workspace, race, requests):
    """One launch per HEAD:SEED[:BATCH], each with a frozen copy of the race's prompt file (RUNBOOK 26)."""
    comfy = workspace.data.get('comfy')
    folder = workspace.root/'design'
    bindings = workspace.require('designBindings')
    (folder/'launches').mkdir(parents=True, exist_ok=True)
    finished = []
    for request in requests:
        head, seed, *rest = request.split(':')
        batch = rest[0] if rest else '2'
        label = f'{stamp()}-{head}-s{seed}'
        spec = folder/'launches'/f'spec-{label}.json'
        spec.write_bytes((folder/f'designs-{race}.json').read_bytes())
        reference = workspace.design_reference(race, head.split('-')[1])
        files = [PYTHON]+[str(REPO/module) for module in DESIGN_MODULES]+sorted(str(path) for path in (HEADKIT/'templates').glob('*.json'))+[str(spec), str(bindings)]
        extra = []
        if reference:
            files.append(str(reference))
            extra = ['--reference', reference]
        input_list = folder/'launches'/f'inputs-{label}.json'
        write_json(input_list, files)
        with gpu_lock(workspace):
            started = time.time()
            data = launch(workspace, folder/'launches'/f'launch-{label}', input_list,
                          [RUN_HEADKIT, 'design', '--bindings', bindings, '--spec', spec, '--head', head, '--seed', seed, '--batch', batch, *extra, '--output', folder/'raw'])
            timing(workspace, f'design {head} s{seed} exit {data["exitCode"]}', started)
        finished.append({'head': head, 'seed': seed, 'exitCode': data['exitCode'], 'elapsedSeconds': data['elapsedSeconds']})
    if comfy:
        request = urllib.request.Request(comfy['url']+'/free', data=b'{"unload_models": true, "free_memory": true}', headers={'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(request, timeout=120).read()
        except OSError as error:  # the designs are done; only the courtesy to the next job failed
            print(f'ComfyUI kept its models: {error}')
    return finished

