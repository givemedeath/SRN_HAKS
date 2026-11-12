"""Attested mode: a ComfyUI that another program started (Comfy Desktop) describes exactly what it runs.

A controlled session proves its deployment before ComfyUI imports anything (managed_startup.py). A server started
elsewhere cannot: its launcher chose the arguments, environment and nodes. Instead it records how it was launched
(arguments, interpreter and the environment that steers Python, CUDA and model loading) beside its source and
runtime census, and the client compares all of it with a snapshot a person approved (tools/headkit/attestation.py).
Nothing here approves anything, and a process that holds a controlled session never uses this mode.
"""
import json
import os
from pathlib import Path
import sys
import uuid
from .managed_startup import SESSION_MODULE, digest, pin
from .source_snapshot import capture_inventory, require

# Variables that steer the interpreter, CUDA/Torch, model loading or these nodes. PATH decides which DLLs load.
STEERING = ('PYTHON', 'CUDA', 'PYTORCH', 'TORCH', 'TRITON', 'HF_', 'SRN_', 'XFORMERS', 'COMFY')
RECORD = 'headkit-attested-launch.json'


def unmanaged():
    """True when no controlled session owns this process (managed_startup.start registers one before import)."""
    return SESSION_MODULE not in sys.modules


def launch_record(folder_paths):
    environment = {key: value for key, value in sorted(os.environ.items())
                   if key.upper() == 'PATH' or key.upper().startswith(STEERING)}
    return {'kind': 'headkit-attested-launch-v1', 'argv': list(sys.argv), 'executable': str(Path(sys.executable).resolve()),
            'basePath': str(Path(folder_paths.base_path).resolve()), 'environment': environment}


def record_path(folder_paths):
    # The user directory is ComfyUI data, outside the source census, and survives the temp-folder cleanup at startup.
    return Path(folder_paths.get_user_directory()).resolve()/'headkit'/RECORD


def attested_session(folder_paths):
    """Write this launch's record and return the session that binds it. The record has no pid, so an identical
    relaunch writes identical bytes and a job collected after a restart still matches its launch."""
    require(unmanaged(), 'A controlled session owns this process: use it, not attested mode')
    record = launch_record(folder_paths); target = record_path(folder_paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=1, sort_keys=True)
    if not target.is_file() or target.read_text(encoding='utf-8') != text: target.write_text(text, encoding='utf-8')
    return {'id': uuid.uuid4().hex, 'pid': os.getpid(), 'configuration': pin(target), 'settingsSha256': digest(record),
            'mode': 'attested'}


def attested_context(folder_paths, session):
    """Re-prove the startup session: same process, record bytes unchanged, launch arguments and environment unchanged."""
    require(isinstance(session, dict) and session.get('mode') == 'attested' and session.get('pid') == os.getpid(),
            'Attested Comfy session changed; prepare again')
    require(pin(session['configuration']['path']) == session['configuration'], 'Attested launch record changed on disk')
    require(digest(launch_record(folder_paths)) == session['settingsSha256'], 'Comfy launch arguments or environment changed')
    return dict(session)


def attested_inventory(folder_paths):
    """The source census of the running ComfyUI: its core and every custom node inside it."""
    core = Path(folder_paths.base_path).resolve(strict=True)
    return capture_inventory(core, [core])
