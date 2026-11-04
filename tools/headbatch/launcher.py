"""Stage, GPU and design launches through the shared-tool launcher, with their locks, guards and timing log."""
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

import guards
from workspace import PYTHON, TOOLS

HEADKIT = TOOLS/'headkit'
RUN_HEADKIT = HEADKIT/'run_headkit.py'
GPU_JOB = Path(__file__).with_name('gpu_job.py')
SLOT_POLL_SECONDS = 15
GPU_POLL_SECONDS = 20
# Only what each job imports: a toolkit edit elsewhere must not invalidate a GPU or design launch in flight (RUNBOOK 40).
GPU_MODULES = ('__init__.py', 'comfy.py', 'common.py', 'gltf.py', 'occiput.py', 'source_inventory.py')
DESIGN_MODULES = ('run_headkit.py', '__init__.py', '__main__.py', 'common.py', 'comfy.py', 'design.py', 'source_inventory.py')


class LaunchFailed(Exception):
    pass


def stamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def timing(workspace, text, started):
    with open(workspace.root/'timings.log', 'a', encoding='utf-8') as log:
        log.write(f"{datetime.now():%H:%M} {text} {int(time.time()-started)} s\n")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1)+'\n', encoding='utf-8', newline='\n')


@contextmanager
def lock(path, owner, poll, sleep=time.sleep):
    """mkdir is atomic, so a lock folder needs no lock server and works on every drive the workspace can use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            path.mkdir()
            break
        except FileExistsError:
            sleep(poll)
    try:
        (path/'owner').write_text(owner, encoding='utf-8')
        yield path
    finally:
        (path/'owner').unlink(missing_ok=True)
        path.rmdir()


@contextmanager
def cpu_slot(workspace, owner, sleep=time.sleep):
    """Take the first free slot of the current limit, which can change while this waits."""
    workspace.locks.mkdir(parents=True, exist_ok=True)
    while True:
        for index in range(workspace.cpu_slots()):
            path = workspace.locks/f'cpu-{index+1}'
            try:
                path.mkdir()
            except FileExistsError:
                continue
            try:
                (path/'owner').write_text(owner, encoding='utf-8')
                yield path
            finally:
                (path/'owner').unlink(missing_ok=True)
                path.rmdir()
            return
        sleep(SLOT_POLL_SECONDS)


def gpu_lock(workspace):
    """One GPU job at a time: designs behind Pixal jobs time out or run out of memory."""
    return lock(workspace.locks/'gpu', f'{os.getpid()} {stamp()}', GPU_POLL_SECONDS)


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
    landmarks = guards.read(workspace.setting('landmarks')) if workspace.setting('landmarks') else None
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
    label = f'{stamp()}-{name}'
    folder = workspace.launches
    marker = folder/f'active-{label}.json'
    write_json(marker, {'heads': heads, 'stages': stages})
    try:
        with cpu_slot(workspace, f'{os.getpid()} {label} {" ".join(heads)}'):
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
    finally:
        marker.unlink(missing_ok=True)
    return {'label': label, 'exitCode': data['exitCode'], 'elapsedSeconds': data['elapsedSeconds'], 'heads': results(output/'stdout.log')}


def results(stdout):
    """Stage statuses from run_headkit's batch output; empty when it printed something else, which the spooler reports (RUNBOOK 117)."""
    try:
        parsed = json.loads(Path(stdout).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    rows = parsed.get('heads', parsed) if isinstance(parsed, dict) else parsed
    return [{'id': row.get('id'), 'error': row.get('error', ''), 'stages': [{'stage': s['stage'], 'status': s['status']} for s in row.get('stages', [])]}
            for row in rows if isinstance(row, dict)]


def run_gpu(workspace, name, arguments):
    """Calibrate, geometry with its occiput check, and appearance for one head on the workspace's ComfyUI."""
    head = workspace.head(name)
    guards.geometry_cap(head)
    comfy = workspace.data.get('comfy')
    if not comfy:
        raise guards.Refused('This step needs "comfy" in workspace.json')
    with gpu_lock(workspace):
        started = time.time()
        label = f'{stamp()}-gpu'
        matte = guards.attempts(head, 'prepare')[-1]/'images'/'design-rgba.png'
        templates = sorted(str(path) for path in (HEADKIT/'templates').glob('*.json'))
        input_list = head/'launches'/f'inputs-{label}.json'
        write_json(input_list, [str(HEADKIT/module) for module in GPU_MODULES]+templates+[str(GPU_JOB), str(matte)])
        job = [GPU_JOB, head, '--comfy-url', comfy['url'], '--comfy-root', workspace.path(comfy['root']), *arguments]
        data = launch(workspace, head/'launches'/f'launch-{label}', input_list, job, workspace.python_environment(packages=True))
        timing(workspace, f'gpu {name} {" ".join(arguments)} exit {data["exitCode"]}', started)
    return data


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
        files = [PYTHON]+[str(HEADKIT/module) for module in DESIGN_MODULES]+sorted(str(path) for path in (HEADKIT/'templates').glob('*.json'))+[str(spec), str(bindings)]
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
        urllib.request.urlopen(request, timeout=120).read()
    return finished

