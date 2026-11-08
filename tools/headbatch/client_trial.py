"""Private, bounded client QA. CPU/GPU leases last until the exact owned client exits."""
from contextlib import ExitStack, contextmanager
from pathlib import Path
import json
import re
import subprocess
import sys
import time

import guards
from head_files import sha, write_json
import launcher
from resource_budget import Budget
from trials import inspection_settings

MAX_SECONDS = 180
CLIENT_BUDGET = {'memoryLimitBytes': 12000000000, 'minimumStartRAMGiB': 6,
                 'minimumFreeRAMGiB': 4}


@contextmanager
def exclusive(workspace):
    """Same acquisition order as GPU jobs; reserve even currently disabled CPU lanes."""
    with ExitStack() as held:
        for number in sorted(workspace.ram_gates()):
            lane = workspace.locks/f'cpu-{number}'
            held.enter_context(launcher.lock(lambda lane=lane: [lane]))
        held.enter_context(launcher.gpu_lock(workspace))
        yield


def existing_clients():
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        "Get-CimInstance Win32_Process -Filter \"Name='nwmain.exe'\" | Select-Object -ExpandProperty ProcessId"],
        capture_output=True, text=True, timeout=15,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise guards.Refused('Cannot establish whether another NWN client is running')
    return result.stdout.strip()


def runtime_files(trial):
    manifest = json.loads((trial/'runtime-manifest.json').read_text(encoding='utf8'))
    if manifest.get('kind') != 'srn-head-trial-client-view':
        raise guards.Refused('Not a private head trial')
    if not re.fullmatch(r'[a-z0-9_]{1,16}', manifest.get('module', '')):
        raise guards.Refused('Invalid private trial module')
    paths = []
    for entry in manifest['files']:
        path = (trial/entry['relativePath']).resolve()
        if not path.is_relative_to(trial.resolve()) or not path.is_file():
            raise guards.Refused('Runtime file escapes the private trial or is missing')
        paths.append((path, entry['sha256']))
    return manifest, paths



def stop_owned(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def supervise(process, budget, stop, seconds=MAX_SECONDS, sleep=time.sleep, clock=time.monotonic):
    """Only terminate the child we created, never a name-based or reused PID."""
    started = clock()
    reason = None
    try:
        while process.poll() is None:
            budget.sample()
            budget.check()
            if stop.exists():
                reason = 'Operator STOP'
                break
            if clock()-started >= seconds:
                reason = 'Client QA time limit reached'
                break
            sleep(1)
    except Exception as error:
        reason = str(error)
    finally:
        stop_owned(process)
    return {'exitCode': process.returncode, 'stopReason': reason,
            'elapsedSeconds': clock()-started}



def archive_client_log(userdir,output):
    """Keep each finished private session's log before another trial can overwrite it."""
    source=Path(userdir)/'logs'/'nwclientLog1.txt';output=Path(output)
    if not source.is_file():raise guards.Refused('Private client log missing; visual QA evidence is incomplete')
    target=output/'client-log.txt'
    if target.exists():raise guards.Refused('Preserve the existing client-session log')
    data=source.read_bytes();target.write_bytes(data)
    digest=sha(target)
    if sha(source)!=digest:raise guards.Refused('Private client log changed during archival')
    write_json(output/'client-log.json',{'source':str(source),'copy':target.name,'sha256':digest})
    return target

def session(config):
    """Worker stays alive with the client; caller holds all leases during this launch."""
    config = Path(config)
    data = json.loads(config.read_text(encoding='utf8'))
    trial, output, client = [Path(data[key]) for key in ('trial', 'output', 'client')]
    if existing_clients():
        raise guards.Refused('Preserve the existing NWN session; close it before private QA')
    manifest, paths = runtime_files(trial)
    for path, digest in paths:
        if sha(path) != digest:
            raise guards.Refused(f'Runtime hash mismatch: {path.name}')
    # Stage a fresh private settings copy; never write the normal game profile.
    settings = trial/'userdir'/'settings.tml'
    if settings.exists():
        (output/'settings-before.tml').write_bytes(settings.read_bytes())
    inspection_settings(settings if settings.exists() else None, output/'settings-applied.tml')
    settings.write_bytes((output/'settings-applied.tml').read_bytes())
    userdir = trial/'userdir'
    lines = ['[Alias]', f'hd0={userdir}']
    for name in ('hak', 'modules', 'override', 'logs', 'currentgame', 'temp', 'localvault', 'database', 'screenshots'):
        folder = userdir/name
        folder.mkdir(exist_ok=True)
        lines.append(f'{name}={folder}')
    (userdir/'nwn.ini').write_text('\n'.join([*lines, '[Game Options]', 'cliententirelog=1'])+'\n', encoding='ascii')
    budget = Budget({**CLIENT_BUDGET, 'gpuIndex': data['gpuIndex']}, output/'memory.json')
    process = None
    try:
        budget.sample()
        budget.admit_prompt()
        process = subprocess.Popen([str(client), '-userdirectory', str(userdir),
                                    '+TestNewModule', manifest['module']],
            cwd=client.parent, creationflags=getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0))
        write_json(output/'running.json', {'pid': process.pid, 'client': str(client),
            'privateUserdir': str(userdir), 'module': manifest['module'], 'maximumSeconds': MAX_SECONDS,
            'runtimeManifestSha256': sha(trial/'runtime-manifest.json'), 'startedUnix': time.time()})
        result = supervise(process, budget, output/'STOP')
        write_json(output/'result.json', {**result, 'pid': process.pid, 'closed': process.poll() is not None})
    finally:
        # Receipt/settings failures after Popen must not release the leases around a live client.
        stop_owned(process)
        budget.close()
        if settings.exists():
            (output/'settings-after.tml').write_bytes(settings.read_bytes())
        if process is not None and process.poll() is not None:
            archive_client_log(userdir,output)
    if result['stopReason'] or result['exitCode'] != 0:
        raise guards.Refused(result['stopReason'] or f"Client exit {result['exitCode']}")


def launch(workspace, name, version):
    if not re.fullmatch(r'[a-z]+', name) or not str(version).isdigit():
        raise guards.Refused('Client needs a trial race and numeric version')
    trial = workspace.root/'trials'/f'{name}-v{version}'
    manifest, files = runtime_files(trial)
    client = workspace.path(workspace.data['game']['client'])
    with exclusive(workspace):
        # Coordinating with other headkit jobs does not grant permission to stop services.
        from headkit.render_device import comfy_idle
        if not comfy_idle(workspace.data['comfy']['url']):
            raise guards.Refused('ComfyUI has running or queued work; client must run alone')
        folder = workspace.root/'trials'/'client-sessions'/f'{name}-{launcher.stamp()}'
        folder.mkdir(parents=True)
        write_json(workspace.root/'runtime'/'current-client.json', {'session': str(folder)})
        config = folder/'session.json'
        write_json(config, {'trial': str(trial), 'output': str(folder), 'client': str(client),
                            'gpuIndex': workspace.data.get('comfy', {}).get('gpuIndex', 0)})
        # Shared-tool launch pins executable, asset bytes and supervisor source.
        sources = [config, trial/'runtime-manifest.json', client,
                   *Path(__file__).parent.rglob('*.py'),
                   *(Path(__file__).parents[1]/'headkit').rglob('*.py'),
                   *[path for path, _ in files]]
        inputs = folder/'inputs.json'
        write_json(inputs, sorted({str(path.resolve()) for path in sources}))
        result = launcher.launch(workspace, folder/'launch', inputs, [Path(__file__), config])
        if result['exitCode']:
            raise guards.Refused(f'Client session stopped; inspect {folder}')
    return folder


if __name__ == '__main__':
    session(sys.argv[1])
