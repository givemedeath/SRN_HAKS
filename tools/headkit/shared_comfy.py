"""The one way any toolkit submits a job to ComfyUI.

Several sessions and the user share one ComfyUI on one GPU (Comfy Desktop, attested: attestation.py; or a
controlled session a driver started). Every submission, from any toolkit, goes through `slot`:

1. take the host GPU lease, a crash-safe named mutex at `<tools root>/locks/gpu-<index>` that headbatch already
   takes for its GPU launches, so no two submitters ever look at the queue at the same moment;
2. wait for an idle queue: another session's job, or the user's, finishes first and is never touched;
3. prove the server, after the wait: its live identity, and for a server the toolkit did not start, the approved
   snapshot (the toolkit's own `comfyAttestation` binding, else the one the shared registry publishes);
4. submit while still holding the lease. The job is in the queue before the lease is released, so the next
   submitter waits for it in step 2.

The lease is not held while a job runs; jobs are collected and rechecked by their own toolkit. Drivers never start,
stop or restart a shared server. `headkit.comfy.Client` refuses a `/prompt` sent outside a slot.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import threading
import time

from . import attestation
from .common import require
from .gpu_lock import locked

LEASE_ENV = 'SRN_GPU_LEASE'  # the lease a launcher holds for the job it started (headbatch), so its child need not wait
WAIT_SECONDS = 2700
_STATE = threading.local()


def lease_path(index=0, root=None):
    require(type(index) is int and index >= 0, 'GPU index must be a nonnegative integer')
    return Path(root or attestation.tools_root())/'locks'/f'gpu-{index}'


def _key(path):
    return os.path.normcase(str(Path(path).resolve()))


def _held(key):
    """'thread' when this thread holds the lease, 'inherited' when a parent process does (it set LEASE_ENV with its
    pid before starting this one), else None. Another thread of the holding process sees its own pid there: not a
    hold of its own, so it waits for the mutex like any other submitter."""
    if key in getattr(_STATE, 'leases', ()): return 'thread'
    marker = os.environ.get(LEASE_ENV, '')
    holder, _, pid = marker.rpartition('|')
    return 'inherited' if holder == key and pid.isdigit() and int(pid) != os.getpid() else None


@contextmanager
def gpu_lease(index=0, root=None, *, limit=WAIT_SECONDS, poll=5.0, say=print, sleep=None):
    """Hold the host GPU lease, waiting up to `limit` seconds for another holder to let it go. Nested holds on this
    thread and inherited holds (a child of the launcher that holds it) pass straight through."""
    path = lease_path(index, root); key = _key(path); sleep = sleep or time.sleep
    if _held(key):
        yield path; return
    started = time.monotonic(); told = False
    while True:
        held = locked(path)
        try:
            held.__enter__(); break
        except FileExistsError:
            require(time.monotonic() - started < limit, f'The shared GPU stayed leased for {limit} s; nothing submitted')
            if not told and say: say(f'waiting for the shared GPU lease ({path}): another session is submitting', flush=True); told = True
            sleep(poll)
    previous = os.environ.get(LEASE_ENV); os.environ[LEASE_ENV] = f'{key}|{os.getpid()}'
    leases = _STATE.__dict__.setdefault('leases', set()); leases.add(key)
    try:
        yield path
    finally:
        leases.discard(key)
        if previous is None: os.environ.pop(LEASE_ENV, None)
        else: os.environ[LEASE_ENV] = previous
        held.__exit__(None, None, None)


def proven(fetch, local=None, root=None):
    """The dispatch proof a submitter keeps for `recheck`: the server's validated live identity and, for an attested
    server, the one approval it was checked against, read once (a later registry approval does not apply to a job
    already running). Refused unless the server is controlled or matches that approval."""
    from .source_inventory import validate_comfy_runtime
    identity = validate_comfy_runtime(fetch('/headkit/runtime-identity'))
    if not attestation.attested(identity): return {'identity': identity, 'approval': None}
    binding = attestation.approval(local, root)
    attestation.check(identity, {'comfyAttestation': binding})
    return {'identity': identity, 'approval': binding}


def live(fetch, local=None, root=None):
    """The server's validated live identity, refused unless it is controlled or matches the approved snapshot."""
    return proven(fetch, local, root)['identity']


def recheck(fetch, proof):
    """Before outputs are accepted: the same server process, still matching the approval frozen at dispatch (or, for
    a controlled session, the same runtime files)."""
    from .source_inventory import validate_comfy_runtime
    current = validate_comfy_runtime(fetch('/headkit/runtime-identity')); before = proof['identity']
    require(current['session']['id'] == before['session']['id'] and current['session']['pid'] == before['session']['pid'],
            'ComfyUI restarted during the job; its outputs are not accepted')
    if proof['approval'] is not None: attestation.check(current, {'comfyAttestation': proof['approval']})
    else: require(current['files'] == before['files'], 'ComfyUI runtime files changed during the job; its outputs are not accepted')
    return current


def idle(fetch):
    queue = fetch('/queue')
    require(isinstance(queue, dict), 'ComfyUI returned no queue')
    return not queue.get('queue_running') and not queue.get('queue_pending')


def wait_idle(fetch, *, limit=WAIT_SECONDS, poll=15.0, say=print, sleep=None):
    started = time.monotonic(); told = False; sleep = sleep or time.sleep
    while not idle(fetch):
        require(time.monotonic() - started < limit, f'The shared ComfyUI queue stayed busy for {limit} s; nothing submitted')
        if not told and say: say('waiting for the shared ComfyUI queue to empty: its jobs are left alone', flush=True); told = True
        sleep(poll)


@contextmanager
def slot(client, local=None, *, prove=True, index=0, root=None, limit=WAIT_SECONDS, poll=15.0, say=print, sleep=None):
    """Lease, wait for idle, prove; submit inside. Yields the dispatch proof (`proven`) to pass to `recheck` before
    outputs are accepted. `prove=False` only where the caller proves the identity itself inside the slot (headkit's
    dispatch verification); it yields None."""
    fetch = getattr(client, 'request', None) or client.call
    with gpu_lease(index, root, limit=limit, say=say, sleep=sleep):
        wait_idle(fetch, limit=limit, poll=poll, say=say, sleep=sleep)
        # Proven after the wait, which can be long: the server may have restarted or changed meanwhile.
        proof = proven(fetch, local, root) if prove else None
        _STATE.depth = getattr(_STATE, 'depth', 0) + 1
        try:
            yield proof
        finally:
            _STATE.depth -= 1


def holding():
    """True inside a slot on this thread."""
    return getattr(_STATE, 'depth', 0) > 0


def status(client, local=None, root=None, index=0):
    """What a person or a driver checks first: the registry, whether the live server matches it, the queue and lease."""
    out = {'endpoint': client.url, 'registry': attestation.published(root)}
    try:
        identity = live(client.request, local, root)
        out['server'] = 'attested, matches the approved snapshot' if attestation.attested(identity) else 'controlled session'
    except Exception as exc:  # report, never raise: this is the diagnostic
        out['server'] = f'refused: {exc}'
    try: out['queueIdle'] = idle(client.request)
    except Exception as exc: out['queueIdle'] = f'unreachable: {exc}'
    mine = _held(_key(lease_path(index, root)))
    if mine: out['lease'] = f'held by this session ({mine})'
    else:
        try:
            with gpu_lease(index, root, limit=0, say=None): out['lease'] = 'free'
        except ValueError: out['lease'] = 'held by another session'
    return out
