"""Stage, GPU and design launches through the shared-tool launcher, with their locks, guards and timing log."""
from contextlib import ExitStack, contextmanager
import ctypes
from datetime import datetime
import json
import math
import os
from pathlib import Path
import subprocess
import time

from gpu_job import SHAPE_NODE, Comfy, file_from
import gpu_contract
import guards
from head_files import complete, current, decision, write_json, sha
from headkit.comfy import locked
from headkit.shared_comfy import gpu_lease
from workspace import PYTHON, REPO, TOOLS

HEADKIT = TOOLS/'headkit'
RUN_HEADKIT = HEADKIT/'run_headkit.py'
GPU_JOB = Path(__file__).with_name('gpu_job.py')
FINISHED_STAGES = ('export', 'native')  # the spooler or a person takes these on; a render waits for its review (RUNBOOK 63)
LOCK_POLL_SECONDS = 2
# Only what each job imports: a toolkit edit elsewhere must not invalidate a GPU or design launch in flight (RUNBOOK 40).
GPU_MODULES = tuple(f'tools/headkit/{name}.py' for name in ('__init__', 'comfy', 'gpu_lock', 'shared_comfy', 'attestation', 'common', 'gltf', 'occiput', 'source_inventory', 'diagnostics', 'rays'))+('tools/shared_tools.py',)
DESIGN_MODULES = tuple(f'tools/headkit/{name}.py' for name in ('run_headkit', '__init__', '__main__', 'common', 'comfy', 'gpu_lock', 'shared_comfy', 'attestation', 'design', 'source_inventory'))+('tools/shared_tools.py',)
DEFAULT_GPU_STAGES = 'calibrate,geometry,appearance'


class LaunchFailed(Exception):
    pass


def stamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S%f')  # labels name files shared with no lock held


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


def free_memory_gb():
    if os.name != 'nt':
        return os.sysconf('SC_AVPHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')/2**30

    class Status(ctypes.Structure):
        _fields_ = [('length', ctypes.c_uint32), ('load', ctypes.c_uint32), ('total', ctypes.c_uint64), ('available', ctypes.c_uint64), ('rest', ctypes.c_uint64*5)]
    status = Status(length=ctypes.sizeof(Status))
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError('GlobalMemoryStatusEx failed')
    return status.available/2**30


def open_slots(workspace, free=None):
    """The slots a job may take now: the current limit, less those whose free-memory gate is closed. Heavy stages page at about 6 GB free (user 2026-10-28)."""
    numbers, gates = range(1, workspace.cpu_slots()+1), workspace.ram_gates()
    available = (free or free_memory_gb)()
    return [workspace.locks/f'cpu-{number}' for number in numbers if available >= gates.get(number, 0)]


def cpu_slot(workspace):
    """The first free slot that is open now: the limit and free memory can both change while this waits."""
    return lock(lambda: open_slots(workspace))


@contextmanager
def gpu_host_lease(workspace):
    """Drain this batch's CPU jobs before a host-RAM-supervised GPU launch."""
    with ExitStack() as held:
        if workspace.data.get('comfy', {}).get('minimumFreeRAMGiB', 0) > 0:
            # cpu-slots can be raised live. Reserve every supported lane in the
            # same order, without starting any CPU work or relaxing its gate.
            for number in sorted(workspace.ram_gates()):
                lane = workspace.locks/f'cpu-{number}'
                held.enter_context(lock(lambda lane=lane: [lane]))
        yield


def gpu_lock(workspace):
    """One GPU job at a time: designs behind Pixal jobs time out or run out of memory. It is the host lease every
    toolkit submits under (headkit.shared_comfy), held until the launch ends; its children inherit the hold."""
    from shared_tools import tools_root
    root,_=tools_root(REPO,workspace.data.get('toolsRoot'))
    index=workspace.data.get('comfy',{}).get('gpuIndex',0)
    if type(index) is not int or index<0:
        raise guards.Refused('GPU index must be a nonnegative integer')
    return gpu_lease(index, root, limit=float('inf'), poll=LOCK_POLL_SECONDS, say=None)


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


def run_stages(workspace, name, stages, heads, approve=None, notes=None, attempt=None):
    """Guards, then one launch for all heads (native compiles every eligible head in one Blender run). Returns the per-head stage results.
    attempt is the attempt of approve the approval was given for: checked under the head lock, so no run can replace it before headkit records the approval."""
    entered=time.monotonic()
    stage_list = stages.split(',')
    dirs = [workspace.head(head) for head in heads]
    bindings = workspace.path(workspace.data['headBindings'])
    landmarks = workspace.landmarks()
    label = f'{stamp()}-{name}'
    folder = workspace.launches
    with guards.head_locks(workspace, heads):
        guards.crlf_in_pinned_code()
        guards.clean_stray_bytecode(bindings)
        for head in dirs:
            guards.loop_budget(head, stage_list, workspace.data.get('loopBudget'))
            guards.palette_rows(workspace, head.name, stage_list)
            if 'repair' in stage_list:
                guards.uv_margin(head)
            if 'ownership' in stage_list:
                guards.ownership_rules(head)
            if 'tone' in stage_list:
                guards.reference_eye_prerequisites(head)
            if attempt:
                guards.approved_attempt(head, approve, attempt)
            if approve == 'repair':
                guards.jaw(head, landmarks)
            if approve == 'ownership' or 'tone' in stage_list:
                guards.ownership_roles(head)
        with cpu_slot(workspace):
            guards.clean_stray_bytecode(bindings)  # strays recur, and the wait for a slot can be long (RUNBOOK 92)
            started = time.time();acquired=time.monotonic()
            head_list = folder/f'heads-{label}.json'
            input_list = folder/f'inputs-{label}.json'
            write_json(head_list, [{'manifest': str(d/'manifest.json'), 'bindings': str(d/'bindings.json'), 'run': str(d/'run')} for d in dirs])
            wanted = stages+(f',{approve}' if approve else '')
            pinned = subprocess.run([PYTHON, '-B', str(RUN_HEADKIT), 'inputs', '--heads', str(head_list), '--output', str(input_list), '--stages', wanted],
                                    env=workspace.python_environment(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if pinned.returncode:
                raise LaunchFailed(f'inputs failed (exit {pinned.returncode}): {pinned.stderr.strip()[-800:]}')
            batch = [RUN_HEADKIT, 'batch', '--heads', head_list, '--stages', stages, '--precompile', folder/f'precompile-{label}']
            if approve:
                batch += ['--approve', approve, f"--notes={notes or ''}"]  # joined: a note can start with a dash
            output = folder/f'launch-{label}'
            ready=time.monotonic()
            data = launch(workspace, output, input_list, batch)
            ended=time.monotonic()
            write_json(output/'headbatch-profile.json',{'queueAndGuardsSeconds':acquired-entered,
                       'inputPreparationSeconds':ready-acquired,'launchWallSeconds':ended-ready,
                       'childSeconds':data['elapsedSeconds'],'launchOverheadSeconds':max(0,ended-ready-data['elapsedSeconds'])})
            timing(workspace, f'cpu {name} {stages}', started)
    return {'label': label, 'exitCode': data['exitCode'], 'elapsedSeconds': data['elapsedSeconds'], 'heads': results(output/'stdout.log'), 'errors': str(output/'stderr.log')}


def results(stdout):
    """Stage statuses from run_headkit's batch output; empty when it printed something else, which the spooler reports (RUNBOOK 117)."""
    try:
        parsed = json.loads(Path(stdout).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    rows = parsed.get('heads', parsed) if isinstance(parsed, dict) else parsed
    return [{'id': row.get('id'), 'error': row.get('error', ''), 'stages': [{key: s[key] for key in ('stage', 'status', 'error', 'attempt', 'reason', 'dependency', 'next') if key in s} for s in row.get('stages', [])]}
            for row in rows if isinstance(row, dict)]


def status(workspace):
    """One line per head. A head whose newest stage finished with no launch queued is waiting on review, which is easy to miss (RUNBOOK 63)."""
    lines = []
    if not workspace.heads.is_dir():
        return lines
    for head in sorted(path for path in workspace.heads.iterdir() if (path/'manifest.json').exists() or (path/'run').is_dir()):
        ledger_path=head/'gpu'/'gpu.json'
        if ledger_path.exists():
            ledger=guards.read(ledger_path)
            last_rejected = (ledger.get('rejectedGeometry') or [{}])[-1]
            if (last_rejected.get('occiput', {}).get('open') and last_rejected.get('submission') == ledger.get('geometrySubmissions')
                    and 'geometry' not in ledger.get('stages', {}) and not guards.head_busy(workspace, head.name)):
                lines.append(f"{head.name} | geometry-{last_rejected['submission']:04d} | REJECTED: open occiput; review raw sheet before reseeding")
                continue
            if 'geometry' in ledger.get('stages',{}) and 'appearance' not in ledger['stages']:
                lines.append(f"{head.name} | geometry-{ledger['stages']['geometry'].get('submission',0):04d} | WAITING ON REVIEW/APPEARANCE")
                continue
        receipts = sorted(head.glob('run/*/attempt-*/receipt.json'), key=lambda path: path.stat().st_mtime)
        if not receipts:
            lines.append(f'{head.name} | no stage yet')
            continue
        newest = receipts[-1]
        receipt = guards.read(newest)
        state = 'failed' if receipt.get('error') else 'ran'
        stage = newest.parts[-3]
        reviewed = (state != 'failed' and current(head, stage) == newest.parent.name
                    and decision(head, stage) == 'approved')
        delivery = receipt.get('result', {}).get('delivery', {})
        full = (delivery.get('diagnostic') is False and delivery.get('sizes') == [2048, 1024]
                and delivery.get('runtimePalette') is True
                and set(delivery.get('modes', [])) == {'clay', 'color-only', 'material-lit'}
                and {'left-three-quarter', 'right-three-quarter', 'left-back-three-quarter', 'right-back-three-quarter'} <= set(delivery.get('views', [])))
        note = ('launch queued or running' if guards.head_busy(workspace, head.name) else
                f'{stage.upper()} REVIEWED; READY FOR NEXT STAGE' if reviewed and stage != 'render' else
                'RENDER REVIEWED; WAITING ON CLIENT TRIAL' if reviewed and full else
                'DIAGNOSTIC REVIEWED; DELIVERY RENDER REQUIRED' if reviewed else 'WAITING ON REVIEW')
        lines.append(f'{head.name} | {stage} {newest.parts[-2]} {state} | {note}')
    return lines


def reused_gpu_inputs(workspace, head, label, stages):
    """What a partial run takes from earlier stages: a frozen ledger, ComfyUI's normalized image and the saved shape (AGENTS: declare consumed inputs)."""
    gpu_contract.stages(','.join(stages))
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
        review = data['stages']['calibrate'].get('cameraReview')
        if review:
            from headkit.common import verify
            verify(review['pins'], fresh=True)
            files.extend(item['path'] for item in review['pins'])
        conditioning = data['stages']['calibrate'].get('conditioning')
        if conditioning:
            for row in conditioning.values():
                if not Path(row['path']).is_file() or sha(row['path']) != row['sha256']:
                    raise guards.Refused('Calibrated conditioning changed; rerun prepare/calibrate')
            files.extend(row['path'] for row in conditioning.values())
        else:
            files.append(str(workspace.path(workspace.data['comfy']['root'])/'input'/'headkit'/head.name/'normalized.png'))
    if 'geometry' in needed:
        gpu_contract.require_geometry_review(head,data)
        geometry = data['stages']['geometry']
        files.extend(row['path'] for row in geometry['files'].values())
        review = data['geometryReview']; evidence = guards.read(review['path'])['evidence']
        report = guards.read(evidence['path'])
        files += [review['path'],evidence['path'],report['sheet']['path'],*[p['path'] for p in report['inputs']]]
    return files, ['--upstream', frozen]


def freeze_prepared(workspace,head,output):
    output.parent.mkdir(parents=True,exist_ok=True)
    done=subprocess.run([PYTHON,'-B',str(GPU_JOB.with_name('gpu_inputs.py')),str(head),str(output)],
                        env=workspace.python_environment(packages=True,tools=True),capture_output=True,text=True)
    if done.returncode:
        raise guards.Refused('Prepared dependency verification failed: '+done.stderr[-1200:])
    return guards.read(output)


def gpu_memory_limits(comfy, profile, stages):
    limits = {key:comfy[key] for key in ('memoryLimitBytes','minimumFreeRAMGiB','minimumStartRAMGiB','gpuIndex') if key in comfy}
    if profile == 'pixal-multiview-v1' and 'geometry' in stages:
        multi_floor = comfy.get('multiviewGeometryStartRAMGiB')
        if multi_floor is not None:
            if type(multi_floor) not in (int,float) or not math.isfinite(multi_floor) or multi_floor <= 0:
                raise guards.Refused('multiviewGeometryStartRAMGiB must be positive and finite')
            limits['minimumStartRAMGiB'] = max(multi_floor, limits.get('minimumStartRAMGiB', 0), limits.get('minimumFreeRAMGiB', 0))
    return limits


def run_gpu(workspace, name, arguments):
    """Calibrate, geometry with its occiput check, and appearance for one head on the workspace's ComfyUI."""
    head = workspace.head(name)
    stages = gpu_contract.stages(arguments[arguments.index('--stages')+1] if '--stages' in arguments else DEFAULT_GPU_STAGES)
    comfy = workspace.data.get('comfy')
    with guards.head_locks(workspace, [name]):
        ledger_file = head/'gpu'/'gpu.json'
        if 'geometry' in stages:  # appearance reuses the saved shape and spends no submission
            guards.geometry_cap(head)
            submitted_before = guards.submissions(head/'gpu', guards.read(ledger_file) if ledger_file.exists() else {})
        if not comfy:
            raise guards.Refused('This step needs "comfy" in workspace.json')
        if (head/'gpu'/'UNRECONCILED').exists():
            raise guards.Refused('Previous GPU prompt is unresolved; reconcile its recorded prompt ID before resuming')
        prepared=[head/'launches'/f'prepared-{stamp()}.json']
        preparation=freeze_prepared(workspace,head,prepared[0])
        admission = []
        if preparation.get('profile') == 'pixal-multiview-v1':
            if not comfy.get('memoryLimitBytes') or 'minimumFreeRAMGiB' not in comfy:
                raise guards.Refused('Set explicit multiview VRAM and free-RAM limits')
            if 'geometry' in stages and '--single-submission' not in arguments:
                raise guards.Refused('Multiview geometry requires --single-submission')
            if 'geometry' in stages and workspace.head_ids()[name][0] == 'troll':
                admission.extend(p['path'] for p in gpu_contract.cardinal_horn_pins(head, preparation))
            if '--detail-camera-attempt' in arguments or '--camera-approval' in arguments:
                raise guards.Refused('Multiview uses its reviewed fixed 20-degree rig')
        if 'calibrate' not in stages:
            ledger=guards.read(head/'gpu'/'gpu.json')
            expected={'receipt':preparation['receipt'],'images':preparation['images']}
            calibrated = ledger.get('stages',{}).get('calibrate',{})
            if calibrated.get('prepared') != expected:
                if stages != ['appearance'] or preparation.get('profile') != 'pixal-multiview-v1':
                    raise guards.Refused('Calibrated inputs differ from the current reviewed prepare; recalibrate')
                pins = gpu_contract.identical_multiview_prepares(head, calibrated, expected)
                replay = head/'launches'/f'calibration-replay-{stamp()}.json'
                write_json(replay, {'original':calibrated['prepared'], 'current':expected,
                                    'purpose':'saved-shape appearance with identical conditioning'})
                admission.extend([str(replay), *[p['path'] for p in pins]])
            if 'appearance' in stages and 'geometry' not in stages:
                gpu_contract.require_geometry_review(head,ledger)
        reviewed_camera = []
        if '--detail-camera-attempt' in arguments or '--camera-approval' in arguments:
            if ('calibrate' not in stages or '--detail-camera-attempt' not in arguments or
                    '--camera-approval' not in arguments or not arguments[arguments.index('--camera-approval')+1].strip()):
                raise guards.Refused('Replaying a reviewed camera requires calibrate, an exact attempt and user approval')
            reviewed_camera = gpu_contract.camera_review_pins(head, arguments[arguments.index('--detail-camera-attempt')+1])
        with gpu_host_lease(workspace), gpu_lock(workspace):
            started = time.time()
            label = f'{stamp()}-gpu'
            templates = sorted(str(path) for path in (HEADKIT/'templates').glob('*.json'))
            input_list = head/'launches'/f'inputs-{label}.json'
            reused, upstream = reused_gpu_inputs(workspace, head, label, stages)
            resources = []
            reused.extend(admission)
            reused.extend(item['path'] for item in reviewed_camera)
            reused += [str(head/'bindings.json'),str(GPU_JOB.with_name('gpu_contract.py')),guards.read(head/'bindings.json')['embree']['path']]
            if 'memoryLimitBytes' in comfy:
                resource_file = head/'launches'/f'resources-{label}.json'
                limits = gpu_memory_limits(comfy, preparation.get('profile'), stages)
                write_json(resource_file, limits)
                resources = ['--resources', resource_file]
                reused += [str(resource_file), str(GPU_JOB.with_name('resource_budget.py')), str(GPU_JOB.with_name('head_files.py'))]
            write_json(input_list, [str(REPO/module) for module in GPU_MODULES]+templates+[str(GPU_JOB), str(GPU_JOB.with_name('resource_budget.py')), str(GPU_JOB.with_name('head_files.py')), *map(str, prepared), *[p['path'] for p in preparation.get('pins',[])]]+reused)
            job = [GPU_JOB, head, '--comfy-url', comfy['url'], '--comfy-root', workspace.path(comfy['root']), *arguments, *upstream, *resources, *(['--prepared', *prepared] if prepared else [])]
            data = launch(workspace, head/'launches'/f'launch-{label}', input_list, job, workspace.python_environment(packages=True))
            timing(workspace, f'gpu {name} {" ".join(arguments)} exit {data["exitCode"]}', started)
        sheet_args = []
        if 'geometry' in stages and data['exitCode'] not in (0,3) and ledger_file.exists():
            rejected = guards.read(ledger_file).get('rejectedGeometry', [])
            if rejected and rejected[-1].get('submission', 0) > submitted_before and rejected[-1].get('occiput', {}).get('open'):
                sheet_args = ['--rejected-geometry', f"geometry-{rejected[-1]['submission']:04d}"]
        if 'geometry' in stages and (data['exitCode'] in (0,3) or sheet_args):
            # Release the GPU lease before waiting on RAM for the CPU-only evidence.
            with cpu_slot(workspace):
                sheet=subprocess.run([PYTHON,'-B',str(GPU_JOB.parent/'review'/'gpuclay.py'),str(head),*sheet_args],
                                     env=workspace.python_environment(packages=True,tools=True),capture_output=True,text=True)
            (head/'launches'/f'launch-{label}'/'geometry-sheet.log').write_text(sheet.stdout+sheet.stderr,encoding='utf-8')
            if sheet.returncode:
                data['exitCode']=1
                print('Raw geometry evidence failed; retry with review --slot gpuclay', name, *sheet_args)
            else:print(sheet.stdout.strip())
    return {**data, 'errors': head/'launches'/f'launch-{label}'/'stderr.log'}


def run_design(workspace, race, requests):
    """One launch per HEAD:SEED[:BATCH]. A refused or invalid one is reported and the rest still run, and ComfyUI frees its models for the next GPU job however they end."""
    comfy = workspace.data.get('comfy')
    folder = workspace.root/'design'
    bindings = workspace.require('designBindings')
    (folder/'launches').mkdir(parents=True, exist_ok=True)
    finished = []
    try:
        for request in requests:
            head, seed, *rest = request.split(':')
            try:
                finished.append(run_one_design(workspace, race, folder, bindings, head, seed, rest[0] if rest else '2'))
            except (guards.Refused, LaunchFailed) as error:
                finished.append({'head': head, 'seed': seed, 'exitCode': 1, 'elapsedSeconds': 0, 'error': str(error)})
    finally:
        if comfy:
            with gpu_lock(workspace):
                try:
                    Comfy(comfy['url'], None).free()
                except OSError as error:  # the designs are done; only the courtesy to the next job failed
                    print(f'ComfyUI kept its models: {error}')
    return finished


def run_one_design(workspace, race, folder, bindings, head, seed, batch):
    """A frozen copy of the race's prompt file, because an edit during a queued launch would otherwise change what it runs (toolkit: re-roll bookkeeping)."""
    label = f'{stamp()}-{head}-s{seed}'
    spec = folder/'launches'/f'spec-{label}.json'
    spec.write_bytes((folder/f'designs-{race}.json').read_bytes())
    profile = guards.read(spec).get('profile', 'flux2-turbo-v1')
    # Head designs on Qwen stay text-only: a configured species reference is neither consumed nor passed (RUNBOOK 244).
    # The compiler itself accepts Qwen references (image edit); this launcher does not use that.
    reference = None if profile == 'qwen21-int8-v1' else workspace.design_reference(race, head.split('-')[1])
    files = [PYTHON]+[str(REPO/module) for module in DESIGN_MODULES]+sorted(str(path) for path in (HEADKIT/'templates').glob('*.json'))+[str(spec), str(bindings)]
    if profile == 'qwen21-int8-v1':
        files += [row['path'] for row in guards.read(bindings).get('models', {}).values()]
    extra = []
    if reference:
        files.append(str(reference))
        extra = ['--reference', reference]
    input_list = folder/'launches'/f'inputs-{label}.json'
    write_json(input_list, files)
    with gpu_lock(workspace):
        if workspace.data.get('comfy'):
            Comfy(workspace.data['comfy']['url'],None).ensure_idle()
        guards.design_cap(folder, head)  # here: two commands queued for the lock must not both spend the last design
        started = time.time()
        data = launch(workspace, folder/'launches'/f'launch-{label}', input_list,
                      [RUN_HEADKIT, 'design', '--bindings', bindings, '--spec', spec, '--head', head, '--seed', seed, '--batch', batch, *extra, '--output', folder/'raw'])
        timing(workspace, f'design {head} s{seed} exit {data["exitCode"]}', started)
    return {'head': head, 'seed': seed, 'exitCode': data['exitCode'], 'elapsedSeconds': data['elapsedSeconds']}

