"""Approved snapshots of a shared ComfyUI that the toolkit did not start (Comfy Desktop).

Several sessions and the user share one ComfyUI. The toolkit node inside it reports an attested identity: its launch
record (arguments, interpreter, steering environment), its source census (core and every custom node) and its
runtime census (Python, Torch, CUDA and every runtime file). A person approves one such identity; every request,
submission and collection must then report exactly that identity, so a job's record names what ran it. When
anything changes (a node installed or updated through Manager, a different model folder, other launch arguments),
jobs are refused with a list of the differences until a new snapshot is approved.

    python tools/headkit/run_headkit.py comfy-attest capture --url URL
    python tools/headkit/run_headkit.py comfy-attest approve --snapshot CAPTURE.json --notes "the user's words"
    python tools/headkit/run_headkit.py comfy-attest status

Captures and approvals live in the shared tools root (`<tools root>/comfy/`), beside the registry
(`shared-comfy.json`) that names the current approval and its endpoint. Every toolkit and session reads that
registry (shared_comfy.py), so one approval serves them all; a `comfyAttestation` binding ({path, sha256}) in a
toolkit's own bindings takes precedence. Nothing here approves: `approve` records the words of the person who
reviewed the capture's summary, and only if the live server still reports the captured identity.
"""
import json
from pathlib import Path
import time
from .common import pin, read, require, sha, verify, write

KIND = 'comfy-attestation-v1'
REGISTRY_KIND = 'shared-comfy-v1'


def tools_root(explicit=None):
    try: from tools.shared_tools import tools_root as find
    except ImportError: from shared_tools import tools_root as find
    return find(None, explicit)[0]


def folder(root=None):
    return Path(root or tools_root())/'comfy'


def published(root=None):
    """The registry every toolkit reads: {kind, endpoint, attestation pin, approvedUtc}, or None before any approval."""
    path = folder(root)/'shared-comfy.json'
    if not path.is_file(): return None
    entry = read(path)
    require(isinstance(entry, dict) and entry.get('kind') == REGISTRY_KIND and isinstance(entry.get('attestation'), dict),
            f'{path} is not a shared ComfyUI registry')
    return entry


def approval(local=None, root=None):
    """The approved snapshot that applies: the toolkit's own `comfyAttestation` binding, else the shared registry's."""
    binding = (local or {}).get('comfyAttestation')
    if binding is None:
        entry = published(root); binding = entry and entry['attestation']
    require(isinstance(binding, dict) and set(binding) == {'path', 'sha256'},
            'This ComfyUI was not started by the toolkit and no approved snapshot is published: '
            'run comfy-attest capture, then have the user approve it')
    return binding


def attested(identity):
    return isinstance(identity, dict) and isinstance(identity.get('session'), dict) and identity['session'].get('mode') == 'attested'


def stable(identity):
    """What must not change between the approval and a job: everything but the per-start session id and pid."""
    configuration = identity['session']['configuration']; verify([configuration])
    launch = read(configuration['path'])
    require(isinstance(launch, dict) and launch.get('kind') == 'headkit-attested-launch-v1', 'Attested launch record is malformed')
    return {'python': identity['python'], 'torch': identity['torch'], 'coveredSourceRoots': identity['coveredSourceRoots'],
            'roots': identity['roots'], 'files': identity['files'], 'comfySourceInventory': identity['comfySourceInventory'],
            'launch': launch}


def _files(rows):
    return {row['path']: row['sha256'] for row in rows}


def differences(approved, current, limit=8):
    """A short, readable list of what changed since the approval."""
    out = []
    for key in ('python', 'torch', 'coveredSourceRoots', 'roots'):
        if approved.get(key) != current.get(key): out.append(f'{key} changed')
    for label, a, b in (('runtime file', _files(approved['files']), _files(current['files'])),
                        ('Comfy source file', _files(approved['comfySourceInventory']['files']),
                         _files(current['comfySourceInventory']['files']))):
        added = sorted(set(b) - set(a)); removed = sorted(set(a) - set(b)); changed = sorted(p for p in set(a) & set(b) if a[p] != b[p])
        for verb, paths in (('added', added), ('removed', removed), ('changed', changed)):
            if paths: out.append(f'{len(paths)} {label}s {verb}: ' + ', '.join(paths[:limit]) + (' ...' if len(paths) > limit else ''))
    la, lb = approved.get('launch', {}), current.get('launch', {})
    if la.get('argv') != lb.get('argv'): out.append(f"launch arguments changed: {la.get('argv')} -> {lb.get('argv')}")
    if la.get('executable') != lb.get('executable'): out.append('interpreter changed')
    ea, eb = la.get('environment', {}), lb.get('environment', {})
    keys = sorted(k for k in set(ea) | set(eb) if ea.get(k) != eb.get(k))
    if keys: out.append('launch environment changed: ' + ', '.join(keys))
    return out or ['identity differs']


def check(identity, local=None, root=None):
    """Refuse an attested identity unless the approved snapshot that applies (approval) names exactly it. A
    controlled one passes through."""
    if not attested(identity): return identity
    binding = approval(local, root)
    verify([binding]); snapshot = read(binding['path'])
    require(snapshot.get('kind') == KIND and snapshot.get('decision') == 'approved' and str(snapshot.get('notes', '')).strip(),
            'The bound ComfyUI attestation is not an approved snapshot')
    current = stable(identity)
    if current != snapshot['identity']:
        raise ValueError('The shared ComfyUI differs from its approved snapshot; approve a new one or restore it. '
                         + '; '.join(differences(snapshot['identity'], current)))
    return identity


def summary(snapshot):
    """What a reviewer reads before approving: versions, launch, node folders, file counts."""
    identity = snapshot['identity']; core = Path(identity['comfySourceInventory']['core'])
    nodes = sorted({Path(row['path']).relative_to(core/'custom_nodes').parts[0] for row in identity['comfySourceInventory']['files']
                    if Path(row['path']).is_relative_to(core/'custom_nodes') and len(Path(row['path']).relative_to(core/'custom_nodes').parts) > 1})
    return {'endpoint': snapshot['endpoint'], 'core': str(core), 'python': identity['python']['version'].split()[0],
            'torch': identity['torch']['version'], 'cuda': identity['torch']['cuda'], 'customNodes': nodes,
            'sourceFiles': len(identity['comfySourceInventory']['files']), 'runtimeFiles': len(identity['files']),
            'launchArguments': identity['launch']['argv'], 'launchEnvironment': sorted(identity['launch']['environment'])}


def capture(client, output=None, root=None):
    from .source_inventory import validate_comfy_runtime
    identity = validate_comfy_runtime(client.request('/headkit/runtime-identity'))
    require(attested(identity), 'This ComfyUI is a controlled session: it needs no attestation')
    snapshot = {'kind': KIND, 'schemaVersion': 1, 'decision': 'pending-review', 'endpoint': client.url, 'identity': stable(identity)}
    output = output or folder(root)/'captures'/f"capture-{time.strftime('%Y%m%d-%H%M%S')}.json"
    write(output, snapshot, fresh=True)
    return {'snapshot': str(output), 'summary': summary(snapshot)}


def approve(client, snapshot_path, notes, output=None, root=None, publish=True):
    """Approve a reviewed capture, only while the live server still reports exactly the captured identity, and
    publish it as the shared registry's current approval."""
    from .source_inventory import validate_comfy_runtime
    require(notes.strip(), "Approval records the reviewer's own words")
    snapshot = read(snapshot_path)
    require(snapshot.get('kind') == KIND and snapshot.get('decision') == 'pending-review', 'Approve a pending capture')
    live = validate_comfy_runtime(client.request('/headkit/runtime-identity'))
    require(attested(live), 'This ComfyUI is a controlled session: it needs no attestation')
    current = stable(live)
    if current != snapshot['identity']:
        raise ValueError('The live ComfyUI changed since the capture; capture again. ' + '; '.join(differences(snapshot['identity'], current)))
    output = output or folder(root)/'approved'/f"approved-{sha(snapshot_path)[:12]}.json"
    write(output, {**snapshot, 'decision': 'approved', 'notes': notes, 'capture': pin(snapshot_path)}, fresh=True)
    result = {'approved': str(output), 'binding': pin(output)}
    if publish:
        entry = {'kind': REGISTRY_KIND, 'endpoint': snapshot['endpoint'], 'attestation': result['binding'],
                 'approvedUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        write(folder(root)/'shared-comfy.json', entry); result['published'] = str(folder(root)/'shared-comfy.json')
    return result
