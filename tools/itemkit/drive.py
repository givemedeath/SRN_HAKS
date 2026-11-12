"""The item driver: every wave step as one command, with machine paths from the item workspace (workspace.py).

    python -m tools.itemkit.drive [--workspace FILE] COMMAND ...

Generation (one GPU job at a time, through the shared ledger; ComfyUI only when this driver started it):
    comfy start|stop|status          image DESIGN colour|clay        condition DESIGN ID [--notes "user's words" --keyed D,C]
    gen ID STAGE --manifest SUFFIX [--attempt aN]                      calibrated ID FOV [--source SUFFIX]
    approve-geometry ID ATTEMPT SRC DST --notes "user's words"          textured ID ATTEMPT SRC --notes ... [--straight DIR]
Processing (CPU, through the verified launcher):
    fit ID SRC DST WORKING DONOR [--overrides JSON] [--measure-only] [--donor-review "user's words"] [--authority "user's words"]
    preview ID SUFFIX                 stage ID SUFFIX STAGE           review ID SUFFIX STAGE approved|rejected NOTES
    chain ID SUFFIX STAGE...          batch ID:SUFFIX... --stages S,S,... [--jobs N]
Fixtures and in-game capture:
    fixture-inputs ID SUFFIX NAME     refixture ID SUFFIX NAME [--capture]       capture FIXTURE_DIR OUTPUT
Families:
    contract FAMILY ID --wave NAME [--visible N]       views GLB OUTPUT [--textured]       decimate IN OUT [--faces N]

Nothing here approves a design: every approval a command records quotes words the user gave (`--notes`,
`--donor-review`), and automatic chain approvals say they are numerical passes only.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.itemkit.workspace import REPO, Workspace

PROCESSING = ('fit', 'reduce', 'unwrap', 'finish', 'bake', 'shadow', 'render', 'export', 'native', 'fixture')
CHAIN_NOTES = ('Automated chain {date}: this stage passed every numerical gate of the pipeline on this manifest. Numerical pass only; '
               'visible quality is reviewed at the render and in-hand stages before any acceptance.')
MAX_JOBS = 3          # independent per-item processing runs at once (user, 2026-10-07); each Blender renders on 4 threads


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''): h.update(block)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def copy_checked(source, target, expected):
    """Copy `source` to `target` unless an exact copy is there; True when `target` then has the `expected` hash.

    The copy lands beside the target and is moved into place, so an interrupted copy never leaves a truncated file
    that a later call would accept by its name; a target with another hash is such a broken copy and is replaced."""
    target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha(target) == expected: return True
    partial = target.with_name(target.name+'.partial'); shutil.copyfile(source, partial)
    if sha(partial) != expected: partial.unlink(); return False
    partial.replace(target); return True


def write_new(path, data):
    path = Path(path)
    if path.exists(): raise SystemExit(f'{path.name} exists: choose a new suffix (manifests are immutable)')
    path.write_text(json.dumps(data, indent=2), encoding='utf-8'); return path


class Driver:
    def __init__(self, workspace):
        self.ws = workspace

    # -- plumbing -------------------------------------------------------------------------------------------------
    def manifest(self, design, suffix): return self.ws.handoff/f'{design}.{suffix}.asset.json'

    def run_dir(self, design, suffix): return self.ws.items/design/f'run-{suffix}'

    def python(self, *args, log=None, check=True, env=None):
        command = [str(self.ws.python), '-B', *map(str, args)]
        out = open(log, 'w', encoding='utf-8') if log else None
        try:
            done = subprocess.run(command, cwd=REPO, env=env or self.ws.environment(), stdout=out or subprocess.PIPE,
                                  stderr=subprocess.STDOUT if out else subprocess.PIPE, text=True)
        finally:
            if out: out.close()
        if check and done.returncode:
            detail = Path(log).read_text(encoding='utf-8', errors='replace')[-1500:] if log else (done.stderr or '')[-1500:]
            raise SystemExit(f'{" ".join(map(str, args[:3]))} failed (exit {done.returncode}):\n{detail}')
        return done

    def launch(self, design, run, name, inputs_args, command, *, kind='processing'):
        """List the consumed inputs, then run one run_itemkit command through the verified shared-tool launcher."""
        run = Path(run); run.mkdir(parents=True, exist_ok=True); rt = self.ws.runtime
        bindings = self.ws.bindings(kind); n = 1
        # A launch that failed early may leave its input listing without a launch folder: skip both.
        while (run/f'launch-{name}-{n}').exists() or (run/f'inputs-{name}-{n}.json').exists(): n += 1
        listing = run/f'inputs-{name}-{n}.json'
        self.python('tools/itemkit/run_itemkit.py', 'inputs', '--bindings', bindings, *inputs_args, '--output', listing)
        out = run/f'launch-{name}-{n}'
        done = self.python('tools/phenotypes/launch_shared_tool.py', '--toolchain', rt/'toolchain.json',
                           '--migration-receipt', rt/'migration.json', '--tool', 'python', '--output', out,
                           '--input-path-list', listing, '--', 'tools/itemkit/run_itemkit.py', *command[:1], '--bindings', bindings,
                           *command[1:], check=False)
        stdout = (out/'stdout.log').read_text(encoding='utf-8', errors='replace') if (out/'stdout.log').exists() else ''
        stderr = (out/'stderr.log').read_text(encoding='utf-8', errors='replace') if (out/'stderr.log').exists() else ''
        if done.returncode:
            # The launcher may fail before it writes its logs (stale migration, bad toolchain): then its own output says why.
            detail = stderr or f'{done.stdout or ""}{done.stderr or ""}'
            raise SystemExit(f'{design}: {command[0]} failed (exit {done.returncode}); {out}\n{detail[-1500:]}')
        return stdout, stderr, out

    # -- generation -----------------------------------------------------------------------------------------------
    def comfy(self, action):
        import urllib.request
        url = self.ws.data['comfy']['url']; pidfile = self.ws.runtime/'comfy.pid'
        def up():
            try: urllib.request.urlopen(url+'/system_stats', timeout=3); return True
            except OSError: return False
        def gpu():
            # One line per GPU; the busiest one decides.
            rows = [line.split(',') for line in subprocess.run(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu', '--format=csv,noheader,nounits'],
                                                                 capture_output=True, text=True).stdout.splitlines() if line.strip()]
            return max(int(r[0]) for r in rows), max(int(r[1]) for r in rows)
        if action == 'status': return {'comfy': 'up' if up() else 'down', 'gpuMiB_util': gpu()}
        if self.ws.data['comfy'].get('shared'):
            # A shared ComfyUI (Comfy Desktop, attested): other sessions and the user queue into it, so this driver
            # never starts or stops it. Every request checks its identity against the bound approved snapshot.
            if action == 'start':
                if not up(): raise SystemExit('The shared ComfyUI is not running: start Comfy Desktop')
                return {'comfy': 'shared', 'url': url}
            if action == 'stop': return {'comfy': 'shared: left running for the other sessions and the user'}
        if action == 'start':
            if up(): raise SystemExit('ComfyUI already answers: not starting a second one')
            used, util = gpu()
            if not os.environ.get('ALLOW_BUSY') and (used >= 5000 or util >= 40): raise SystemExit(f'GPU busy ({used} MiB, {util}%): not starting')
            c = self.ws.data['comfy']; n = 1
            while (self.ws.runtime/f'comfy-run-{n}.log').exists() or (self.ws.runtime/f'comfy-run-{n}.json').exists(): n += 1
            log = self.ws.runtime/f'comfy-run-{n}.log'
            with open(log, 'w') as handle:     # the child keeps its own copy of the handle
                process = subprocess.Popen([str(self.ws.path(c['python'])), '-I', '-B', str(self.ws.path(c['startup'])), '--config',
                                            str(self.ws.path(c['config'])), '--receipt', str(self.ws.runtime/f'comfy-run-{n}.json')],
                                           stdout=handle, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            pidfile.write_text(str(process.pid))
            for _ in range(90):
                if up(): return {'comfy': 'up', 'pid': process.pid, 'run': n}
                if process.poll() is not None: break
                time.sleep(5)
            # Stop what this call started and forget its PID: a stale PID file could later name an unrelated process.
            if process.poll() is None: subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
            pidfile.unlink(missing_ok=True)
            raise SystemExit(f'ComfyUI did not come up; see {log}')
        if action == 'stop':
            if not pidfile.exists(): return {'comfy': 'no PID file: nothing this driver started'}
            pid = int(pidfile.read_text())
            # A PID outlives its process: kill it only while it is still the startup script this driver launched.
            startup = Path(self.ws.path(self.ws.data['comfy']['startup'])).name.lower()
            query = subprocess.run(['powershell', '-NoProfile', '-Command', f'(Get-CimInstance Win32_Process -Filter "ProcessId={pid}").CommandLine'],
                                   capture_output=True, text=True)
            # A failed query says nothing about the process: keep the PID file rather than forget a running ComfyUI.
            if query.returncode: raise SystemExit(f'Could not read the command line of PID {pid}: {query.stderr.strip()[-300:]}')
            if startup not in query.stdout.strip().lower():
                if up(): raise SystemExit(f'PID {pid} is not the ComfyUI this driver started, yet ComfyUI answers: stop it yourself')
                pidfile.unlink(); return {'comfy': f'PID {pid} is no longer the ComfyUI this driver started: nothing stopped, stale PID file removed'}
            subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True); pidfile.unlink()
            time.sleep(3)
            if up(): raise SystemExit('ComfyUI still answering after stopping the process this driver started')
            return {'comfy': 'stopped', 'pid': pid}
        raise SystemExit('comfy start|stop|status')

    def wait_idle(self, limit=2700, poll=15):
        """A shared queue may be running another session's or the user's job: wait for it instead of failing the
        submission, which refuses a busy queue (and leaves no ledger record when it does)."""
        import urllib.request
        url = self.ws.data['comfy']['url']; started = time.monotonic()
        while True:
            with urllib.request.urlopen(url+'/queue', timeout=10) as response: queue = json.loads(response.read())
            if not queue.get('queue_running') and not queue.get('queue_pending'): return
            if time.monotonic() - started > limit: raise SystemExit('The shared ComfyUI queue stayed busy for 45 minutes: try again later')
            time.sleep(poll)

    def gen(self, design, stage, suffix, attempt='a1'):
        """request -> submit -> collect for one generation stage; geometry also gets a shape check and clay views."""
        manifest = self.manifest(design, suffix); run = self.ws.items/design/f'{stage}-{attempt}'
        if (run/'job/submission.json').exists(): raise SystemExit(f'{design} {stage}-{attempt} already submitted: reconcile it instead')
        flags = {'appearance': ['--appearance-donor'], 'export': ['--working-shell']}.get(stage, [])
        common = ['--manifest', manifest, '--stage', stage]
        self.launch(design, run, 'request', common, ['request', '--manifest', manifest, '--stage', stage, '--output', run/'request', *flags], kind='generation')
        if self.ws.data['comfy'].get('shared'): self.wait_idle()
        out, _, _ = self.launch(design, run, 'submit', [*common, '--extra', run/'request'],
                                ['submit', '--request', run/'request', '--output', run/'job'], kind='generation')
        token = re.search(r'"token": "([0-9a-f]+)"', out); token = token and token.group(1)
        if not token: raise SystemExit(f'{design}: no token from submit\n{out[-800:]}')
        self.launch(design, run, 'collect', [*common, '--extra', run/'job/submission-intent.json'],
                    ['collect', '--token', token, '--output', run/'job', '--wait'], kind='generation')
        collection = read(run/'job/collection.json'); result = {'design': design, 'stage': stage, 'token': token, 'state': collection['state']}
        if stage == 'geometry':
            glb = next(o['path'] for o in collection['outputs'] if o['path'].endswith('.glb')); family = read(self.ws.handoff/read(manifest)['familyProfile']['path'])['family']
            check = self.ws.items/design/f'geometry-{attempt}-shape-check.json'
            self.python('-m', 'tools.itemkit.straightness', 'check', glb, '--family', family, '--output', check, check=False)
            result['views'] = self.views(glb, self.ws.items/design/f'geometry-{attempt}-views')
            if check.exists(): result['shape'] = read(check)['metrics']
        return result

    def calibrated(self, design, fov, source='wave1-v2-contract'):
        if not 25 <= fov <= 70: raise SystemExit('A reviewed geometry FOV is between 25 and 70 degrees')
        m = read(self.manifest(design, source))
        if m['camera'] != {'reviewed': False, 'fovDegrees': None}: raise SystemExit('Source manifest already has a camera')
        m['camera'] = {'reviewed': True, 'fovDegrees': float(fov)}
        return str(write_new(self.manifest(design, 'calibrated-v2'), m))

    def approve_geometry(self, design, attempt, src, dst, notes):
        """Bind the collected clay to a manifest with the user's approval words."""
        if not notes.strip(): raise SystemExit("--notes must quote the user's clay approval")
        c = read(self.ws.items/design/f'geometry-{attempt}/job/collection.json')
        if c['state'] != 'complete': raise SystemExit('Geometry job not complete')
        (glb,), (npz,) = [o for o in c['outputs'] if o['path'].endswith('.glb')], [o for o in c['outputs'] if o['path'].endswith('.npz')]
        m = read(self.manifest(design, src))
        for role, o, name in (('geometryRaw', glb, 'geometry-raw.glb'), ('shape', npz, 'shape.npz')):
            target = self.ws.handoff/'generated'/design/f'geometry-{attempt}'/name
            if not copy_checked(o['path'], target, o['sha256']): raise SystemExit(f'{role} copy differs from the collected output')
            m['inputs'][role] = {'path': target.relative_to(self.ws.handoff).as_posix(), 'sha256': o['sha256']}
        m['approval']['generatedGeometry'] = {'decision': 'approved', 'geometryRawSha256': glb['sha256'], 'shapeSha256': npz['sha256'], 'notes': notes}
        return str(write_new(self.manifest(design, dst), m))

    def donor_manifest(self, design, src, dst, notes, attempt='a1'):
        import numpy as np
        c = read(self.ws.items/design/f'appearance-{attempt}/job/collection.json')
        if c['state'] != 'complete': raise SystemExit('Appearance job not complete')
        by = {Path(o['path']).name: o for o in c['outputs']}; m = read(self.manifest(design, src))
        if by['node-961_00001.glb']['sha256'] != m['inputs']['geometryRaw']['sha256']: raise SystemExit('Appearance ran on another shape')
        for role, node, name in (('geometryDonor', 'node-922_00001.glb', 'donor-200k-768.glb'), ('field', 'node-962_00001.npz', 'appearance-field.npz')):
            o = by[node]; target = self.ws.handoff/'generated'/design/f'appearance-{attempt}'/name
            if not copy_checked(o['path'], target, o['sha256']): raise SystemExit(role+' copy differs')
            m['inputs'][role] = {'path': target.relative_to(self.ws.handoff).as_posix(), 'sha256': o['sha256']}
        with np.load(self.ws.handoff/m['inputs']['field']['path']) as z: lo, hi = float(z['attrs'].min()), float(z['attrs'].max())
        if not (-.05 <= lo and hi <= 1.065): raise SystemExit(f'Appearance field out of the decoder range: {lo}..{hi}')
        m['approval']['sourceDonor'] = {'decision': 'approved', 'geometryDonorSha256': m['inputs']['geometryDonor']['sha256'],
                                        'fieldSha256': m['inputs']['field']['sha256'], 'notes': notes + f' Field value range measured {lo:.4f}..{hi:.4f}.'}
        m['processing']['sourceDonorTopologyPolicy'] = 'sampling-surface-v1'
        m['processing']['sourceFieldPolicy'] = {'allowDecoderOvershoot': True, 'fieldSha256': m['inputs']['field']['sha256'], 'minimum': -.05, 'maximum': 1.065}
        return str(write_new(self.manifest(design, dst), m))

    def textured(self, design, attempt, src, notes, straight=None):
        """Approved clay -> appearance (with the 200K donor) -> donor manifest -> CPU colour bake -> textured views."""
        if not notes.strip(): raise SystemExit("--notes must quote the user's clay approval")
        collection = self.ws.items/design/f'geometry-{attempt}/job/collection.json'
        if not collection.exists(): raise SystemExit(f'{design}: geometry {attempt} was never collected')
        if not self.manifest(design, 'geometry-approved-v1').exists(): self.approve_geometry(design, attempt, src, 'geometry-approved-v1', notes)
        collected = read(collection)
        glb = next(o['sha256'] for o in collected['outputs'] if o['path'].endswith('.glb'))
        if read(self.manifest(design, 'geometry-approved-v1'))['approval']['generatedGeometry']['geometryRawSha256'] != glb:
            raise SystemExit(f'geometry-approved-v1 binds another attempt than {attempt}: this chain continues only one approved clay')
        if not (self.ws.items/design/'appearance-a1/job/collection.json').exists():
            self.comfy('start')
            try: self.gen(design, 'appearance', 'geometry-approved-v1')
            finally: self.comfy('stop')
        if not self.manifest(design, 'donor-v1').exists():
            self.donor_manifest(design, 'geometry-approved-v1', 'donor-v1', 'Automated chain: 200K/768 UDF donor and colour field from the appearance job '
                                'on the approved clay (raw mesh hash checked identical). Visual review of the textured result is still required.')
        run = self.run_dir(design, 'donor-v1')
        # The donor of the attempt the run's state records: attempt folders are not ordered, and an older or failed
        # attempt may hold a textured-donor.glb too.
        recorded = lambda: (read(run/'state.json')['stages'].get('donor') if (run/'state.json').exists() else None)
        if recorded() is None: self.stage(design, 'donor-v1', 'donor')
        donor = next(Path(recorded()['path']).parent.rglob('textured-donor.glb'))
        family = read(self.ws.handoff/read(self.manifest(design, 'donor-v1'))['familyProfile']['path'])['family']
        for kind, name in (('straighten', 'straightened'), ('thin', 'thinned')):
            mapping = Path(straight)/f'{kind}-map.npz' if straight else None
            if mapping and mapping.exists():
                out = self.ws.items/design/f'donor-v1-{name}'
                if out.exists() and not (out/f'{name}.glb').exists():
                    raise SystemExit(f'{out} holds an unfinished {kind} run: move it aside first')
                if not out.exists():
                    self.python('-m', 'tools.itemkit.straightness', kind, donor, out, '--map', mapping, *(('--family', family) if kind == 'straighten' else ()))
                donor = out/f'{name}.glb'
        return {'texturedDonor': str(donor), 'views': self.views(donor, donor.parent/'textured-views', textured=True)}

    def image(self, design, kind):
        """One Codex built-in image generation call from the references' PROMPTS.md."""
        refs = self.ws.setting('references'); codex = self.ws.setting('codex')
        if not refs or not codex: raise SystemExit('Workspace needs references and codex')
        source, target = {'colour': ('current-side-view.png', 'detail-original.png'), 'clay': ('detail-original.png', 'clay-original.png')}[kind]
        folder = refs/design
        if not (folder/source).exists(): raise SystemExit(f'missing {design}/{source}')
        if (folder/target).exists(): raise SystemExit(f'{design}/{target} exists; move it aside first')
        sections = {h.strip().lower(): body for h, body in re.findall(r'^## (.+?)\n(.*?)(?=^## |\Z)', (refs/'PROMPTS.md').read_text(encoding='utf-8'), re.S | re.M)}
        blocks = re.findall(r'```\n(.*?)```', sections[design.lower()], re.S)
        if len(blocks) != 2: raise SystemExit('PROMPTS.md needs one colour and one clay prompt per design')
        prompt = (f'Use your built-in image generation tool exactly once, with the attached image as the input reference image, a square output, '
                  f'and the image prompt below used verbatim.\nThen copy the generated PNG into the current directory as {target}. Do not create, edit '
                  f'or delete any other file, do not post-process the image, and do not make a second image. Reply with the saved path only.\n\n'
                  f'IMAGE PROMPT:\n{blocks[["colour", "clay"].index(kind)]}')
        n = 1
        while (folder/f'run-{kind}-{n}').exists(): n += 1
        run = folder/f'run-{kind}-{n}'; run.mkdir()
        (run/'prompt.txt').write_text(prompt, encoding='utf-8')
        with open(run/'prompt.txt', encoding='utf-8') as stdin, open(run/'codex.log', 'w', encoding='utf-8') as log:
            done = subprocess.run([str(codex), 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', str(folder), '-i', str(folder/source),
                                   '-o', str(run/'last-message.txt'), '-'], stdin=stdin, stdout=log, stderr=subprocess.STDOUT)
        if done.returncode or not (folder/target).exists(): raise SystemExit(f'Codex image failed; see {run/"codex.log"}')
        return {'image': str(folder/target), 'run': str(run)}

    def condition(self, design, did, source='wave1-v2-contract', notes=None, keyed=None):
        """Without --notes: key and measure the pair, then stop for review. With the user's words and the keyed hashes: condition."""
        from tools.itemkit.oblique import condition
        return condition(self.ws.setting('references')/design, self.ws.handoff, did, source, notes=notes,
                         keyed_sha256=keyed.split(',') if keyed else None)

    # -- processing -----------------------------------------------------------------------------------------------
    def stage(self, design, suffix, stage):
        m = self.manifest(design, suffix); run = self.run_dir(design, suffix)
        out, err, _ = self.launch(design, run, stage, ['--manifest', m, '--run', run, '--stage', stage],
                                  ['run', '--manifest', m, '--run', run, '--stage', stage])
        return {'design': design, 'stage': stage, 'stdout': out[-1500:]}

    def review(self, design, suffix, stage, decision, notes):
        m = self.manifest(design, suffix); run = self.run_dir(design, suffix)
        out, _, _ = self.launch(design, run, f'review-{stage}', ['--manifest', m, '--run', run, '--stage', stage],
                                ['review', '--manifest', m, '--run', run, '--stage', stage, '--decision', decision, '--notes', notes])
        return json.loads(out[out.index('{'):]) if '{' in out else out

    def chain(self, design, suffix, stages, notes=None):
        m = self.manifest(design, suffix); run = self.run_dir(design, suffix); started = time.monotonic()
        notes = notes or CHAIN_NOTES.format(date=time.strftime('%Y-%m-%d'))
        _, err, out = self.launch(design, run, 'chain', ['--manifest', m, '--run', run, '--stages', *stages],
                                  ['chain', '--manifest', m, '--run', run, '--stages', *stages, '--notes', notes])
        rows = [json.loads(line) for line in err.splitlines() if line.startswith('{"stage"')]
        return {'design': design, 'suffix': suffix, 'seconds': round(time.monotonic() - started), 'stages': rows, 'launch': str(out)}

    def batch(self, items, stages, jobs=2):
        """Chains for several designs at once (at most MAX_JOBS); each item's log stays in its own run folder."""
        if not 1 <= jobs <= MAX_JOBS: raise SystemExit(f'--jobs is 1..{MAX_JOBS}')
        pairs = [item.split(':') for item in items]
        bad = [item for item, pair in zip(items, pairs) if len(pair) != 2 or not all(pair)]
        if bad: raise SystemExit(f'batch items are ID:SUFFIX, not {bad}')
        def one(pair):
            design, suffix = pair
            try: return self.chain(design, suffix, stages)
            except (SystemExit, Exception) as error: return {'design': design, 'suffix': suffix, 'failed': str(error)[-800:]}
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=jobs) as pool: results = list(pool.map(one, pairs))
        return {'jobs': jobs, 'seconds': round(time.monotonic() - started), 'items': results}

    def fit(self, design, src, dst, working, donor, overrides=None, *, measure_only=False, donor_review=None, authority=None):
        """Measure the fit; when the grip departs, learn the fit worker's digest by its measure-only pass and bind it."""
        from tools.headkit.gltf import mesh
        from tools.itemkit import fit_manifest
        overrides = read(overrides) if isinstance(overrides, (str, Path)) else dict(overrides or {})
        m = read(self.manifest(design, src)); family = read(self.ws.handoff/m['familyProfile']['path'])
        data = fit_manifest.measure(m, family, mesh(working), overrides)
        summary = {k: data[k] for k in ('method', 'landmarks', 'scale', 'nativeLength', 'stockLength', 'joinY', 'sizingAuthority', 'departurePending')}
        summary['probeThickness'] = [round(p['measuredThickness'], 4) for p in data['thicknessProbes']]
        if measure_only: return summary
        words = authority or overrides.get('uniformAuthority')
        if data['departurePending'] and not overrides.get('departureDigest'):
            measurement = self._measured_candidate(design, dst+'-measure', working, donor, overrides)
            if measurement is None:
                candidate, _ = fit_manifest.write(self.ws.handoff, design, src, dst+'-measure', working, donor, overrides,
                                                  notes_authority=authority, measured=data)     # same shell and overrides
                self._approve_donor(candidate, donor_review)
                measurement = self.preview(design, dst+'-measure')
            overrides['departureDigest'] = measurement['measurementDigest']; summary['measure'] = measurement
        if overrides.get('departureDigest') and not words:
            # The grip departure is an approval: it is bound only with the user's own words (--authority).
            summary['departureNeedsAuthority'] = True; return summary
        out, data = fit_manifest.write(self.ws.handoff, design, src, dst, working, donor, overrides, notes_authority=authority)
        self._approve_donor(out, donor_review)
        summary.update(manifest=str(out), departureDigest=overrides.get('departureDigest'))
        return summary

    def _approve_donor(self, path, words):
        """Bind the user's review of the exact textured donor and working shell, when they gave one."""
        if not words: return
        m = read(path)
        for role in ('texturedDonor', 'workingMesh'):
            m['approval'][role] = {'decision': 'approved', 'sha256': m['inputs'][role]['sha256'], 'notes': words}
        Path(path).write_text(json.dumps(m, indent=2), encoding='utf-8')

    def _measured_candidate(self, design, suffix, working, donor, overrides):
        """The worker measurement of an existing `<DST>-measure` candidate made from these same inputs, else None.

        A fit that stopped for the user's departure authority is re-run with --authority; it reuses the candidate
        (and its newest measurement) instead of failing on the existing manifest."""
        if not self.manifest(design, suffix).exists(): return None
        record = read(self.ws.handoff/'generated'/design/suffix/'fit-data.json')
        if (record['working'], record['donor'], record['overrides']) != (sha(working), sha(donor), json.loads(json.dumps(overrides))):
            raise SystemExit(f'{design}.{suffix} was measured from other inputs: choose a new DST')
        done = sorted(self.run_dir(design, suffix).glob('measure-*/worker/measurement.json'), key=lambda p: int(p.parts[-3].split('-')[1]))
        return self._measurement(done[-1]) if done else self.preview(design, suffix)

    def _measurement(self, path):
        result = read(path)
        return {'measurementDigest': result['measurementDigest'], 'departure': result['departure'], 'nativeLength': round(result['nativeLength'], 4),
                'gripLength': round(result['gripLength'], 4), 'preview': {k: v['path'] for k, v in result['preview'].items()}}

    def preview(self, design, suffix):
        """The fit worker's measure-only pass on a manifest: grip digest, native length and two preview images."""
        m = self.manifest(design, suffix); run = self.run_dir(design, suffix); n = 1
        while (run/f'measure-{n}').exists(): n += 1
        self.launch(design, run, 'measure-fit', ['--manifest', m, '--run', run, '--stage', 'fit'],
                    ['measure-fit', '--manifest', m, '--run', run, '--output', run/f'measure-{n}'])
        return self._measurement(run/f'measure-{n}/worker/measurement.json')

    # -- fixtures -------------------------------------------------------------------------------------------------
    def fixture_inputs(self, design, suffix, name):
        """The fixture's own inputs (template module, both Human reviewers, nwscript, comparisons) and the fixture HAK pins
        as a fixture-inputs document beside the manifests. The processing bindings are never modified."""
        fx = self.ws.data.get('fixture', {}); erf = self.ws.setting('erf')
        if not erf: raise SystemExit('Workspace needs erf')
        doc_path = self.ws.handoff/f'{design}.{name}.fixture-inputs.json'
        if doc_path.exists(): raise SystemExit(f'{doc_path.name} exists: choose a new name (fixture inputs are immutable)')
        # The review HAKs are built once and shared (the bindings pin them); everything a document pins of its own lives in
        # its own folder, so a later document never rewrites bytes an earlier one pinned.
        shared = self.ws.handoff/'fixture-v3'; shared.mkdir(exist_ok=True)
        # No document pins this folder yet (doc_path does not exist), so a failed earlier attempt's files may be replaced.
        own = f'fixture-inputs/{design}.{name}'; folder = self.ws.handoff/own; folder.mkdir(parents=True, exist_ok=True)
        tests = self.ws.path(fx.get('testModules', REPO/'test-modules/weapon-waves')); packs = self.ws.path(fx.get('packs', REPO/'output'))
        haks = {}
        for hak in ('sw_reviewenv', 'sw_f7motion'):
            target = shared/f'{hak}.hak'
            if not target.exists():
                # Built beside the target and moved into place: an interrupted build never leaves a HAK later documents pin.
                partial = target.with_suffix('.partial.hak'); partial.unlink(missing_ok=True)
                subprocess.run([str(erf), '-c', '-e', 'HAK', '-f', str(partial), str(tests/'haks'/hak)], check=True); partial.replace(target)
            haks[hak] = {'path': str(target), 'sha256': sha(target)}
        for hak in ('srn_weapon', 'srn_body_tex', 'srn_body', 'srn_2da'): haks[hak] = {'path': str(packs/f'{hak}.hak'), 'sha256': sha(packs/f'{hak}.hak')}
        profile = self.ws.handoff/read(self.manifest(design, suffix))['familyProfile']['path']; contract = profile.parent
        stack = read(contract/read(profile)['native']['stack']['path']); (layer,) = [l for l in stack['layers'] if l.get('name') == 'private-floor-template']
        with tempfile.TemporaryDirectory(prefix='fixture-template-') as tmp:
            for row in layer['resources']: shutil.copyfile(contract/row['file']['path'], Path(tmp)/row['resource'])
            template = folder/'fixture-template.mod'; template.unlink(missing_ok=True)
            subprocess.run([str(erf), '-c', '-e', 'MOD', '-f', str(template), tmp], check=True)
        copies = [(tests/'module/sr_it_male.utc', 'sr_it_male.utc'), (tests/'module/sr_it_female.utc', 'sr_it_female.utc'),
                  (contract/'stock/nwscript.nss', 'nwscript.nss')]
        comparisons = fx.get('comparisons', ['../../srn_weapon/sr_cfs.uti', '../../srn_weapon/sr_cougar.uti'])
        # Indexed names: two comparisons may share a file name (the fixture takes each one's resref from its own tag).
        copies += [(self.ws.path(c), f'comparison{i}-{Path(c).name}') for i, c in enumerate(comparisons)]
        for source, target in copies: shutil.copyfile(source, folder/target)
        rel = lambda n: {'path': f'{own}/{n}', 'sha256': sha(folder/n)}
        inputs = {'fixtureTemplate': rel('fixture-template.mod'), 'maleCreature': rel('sr_it_male.utc'), 'femaleCreature': rel('sr_it_female.utc'),
                  'nwscript': rel('nwscript.nss')}
        for i, c in enumerate(comparisons): inputs['comparisonBlueprint'+(str(i) if i else '')] = rel(f'comparison{i}-{Path(c).name}')
        # The HAK pins travel in the document, not the bindings: every processing receipt pins the bindings file, so
        # editing it would make the native chain a rebuild starts from stale.
        doc = write_new(doc_path, {'kind': 'fixture-inputs', 'inputs': inputs, 'fixtureHaks': haks})
        return {'fixtureInputs': str(doc), 'haks': {k: v['sha256'][:10] for k, v in haks.items()}}

    def refixture(self, design, suffix, name, capture=False):
        """A new fixture from the run's reviewed native package, then (optionally) the unattended in-game capture."""
        m = self.manifest(design, suffix); run = self.run_dir(design, suffix); doc = self.ws.handoff/f'{design}.{name}.fixture-inputs.json'
        if not doc.exists(): self.fixture_inputs(design, suffix, name)
        n = 1
        while (run/f'refixture-{n}').exists(): n += 1
        self.launch(design, run, 'refixture', ['--manifest', m, '--run', run, '--stage', 'fixture', '--extra', doc],
                    ['refixture', '--manifest', m, '--run', run, '--fixture-inputs', doc, '--output', run/f'refixture-{n}'])
        result = {'fixture': str(run/f'refixture-{n}/fixture')}
        if capture:
            k = 1
            while (run/f'refixture-{n}/captures-{k}').exists(): k += 1
            result['capture'] = self.capture(run/f'refixture-{n}/fixture', run/f'refixture-{n}/captures-{k}')
        return result

    def capture(self, fixture, output):
        nwn = self.ws.setting('nwnRoot')
        if not nwn: raise SystemExit('Workspace needs nwnRoot')
        done = self.python('-m', 'tools.itemkit.client_capture', fixture, output, '--nwn-root', nwn, check=False)
        if done.returncode: raise SystemExit(f'Capture failed:\n{(done.stdout or "")[-800:]}{(done.stderr or "")[-800:]}')
        result = json.loads(done.stdout[done.stdout.index('{'):])      # the capture run already made the contact sheets
        return {'result': result, 'sheets': result['sheets']}

    # -- families and helpers -------------------------------------------------------------------------------------
    def contract(self, family, design, wave, visible=None):
        from tools.itemkit.family_contract import build
        return build(self.ws, family, design, wave, visible=visible)

    def views(self, glb, output, textured=False):
        """Eight orthographic Blender views and a contact sheet (clay, or the textured donor's colour)."""
        output = Path(output)
        # Blender's own Python: a workspace PYTHONPATH would load the bank's numpy into it and break the glTF importer.
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
        done = subprocess.run([str(self.ws.blender), '-b', '--factory-startup', '--python-exit-code', '1', '-P',
                               str(REPO/'tools/itemkit/preview_views.py'), '--', str(glb), str(output), 'textured' if textured else 'clay'],
                              capture_output=True, text=True, env=env)
        if done.returncode: raise SystemExit('View render failed:\n'+(done.stdout + done.stderr)[-1500:])
        from tools.itemkit.preview_views import sheet
        bounds = next((line for line in done.stdout.splitlines() if line.startswith('bounds')), '')
        return {'sheet': str(sheet(output)), 'bounds': bounds}

    def decimate(self, source, target, faces=None):
        from tools.headkit.gltf import mesh, write_mesh
        from tools.itemkit.autofit import WORKING_SHELL_TRIANGLES, thin_shell
        import pymeshlab, igl, numpy as np
        if Path(target).exists(): raise SystemExit(f'{target} exists: choose a new output (a working shell may be pinned)')
        faces = faces or WORKING_SHELL_TRIANGLES
        m = mesh(source); v, f, report = thin_shell(m['positions'], m['faces'], pymeshlab, faces,
                                                    distances=lambda points, vv, ff: np.sqrt(igl.point_mesh_squared_distance(points, vv, ff)[0]))
        write_mesh(target, v, f); return {**report, 'output': str(target), 'sha256': sha(target)}


def stage_list(text):
    stages = [s for s in text.split(',') if s]
    unknown = [s for s in stages if s not in PROCESSING]
    if not stages or unknown: raise argparse.ArgumentTypeError(f'stages are a comma-separated subset of {",".join(PROCESSING)}')
    return stages


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument('--workspace'); c = p.add_subparsers(dest='command', required=True)
    s = c.add_parser('comfy'); s.add_argument('action', choices=['start', 'stop', 'status'])
    s = c.add_parser('image'); s.add_argument('design'); s.add_argument('kind', choices=['colour', 'clay'])
    s = c.add_parser('condition'); s.add_argument('design'); s.add_argument('id'); s.add_argument('--source', default='wave1-v2-contract')
    s.add_argument('--notes', help="the user's review of the keyed pair"); s.add_argument('--keyed', help='DETAIL_SHA,CLAY_SHA from the first call')
    s = c.add_parser('gen'); s.add_argument('id'); s.add_argument('stage', choices=['calibrate', 'geometry', 'appearance', 'export'])
    s.add_argument('--manifest', required=True, help='manifest suffix'); s.add_argument('--attempt', default='a1')
    s = c.add_parser('calibrated'); s.add_argument('id'); s.add_argument('fov', type=float); s.add_argument('--source', default='wave1-v2-contract')
    s = c.add_parser('approve-geometry'); [s.add_argument(k) for k in ('id', 'attempt', 'src', 'dst')]; s.add_argument('--notes', required=True)
    s = c.add_parser('textured'); [s.add_argument(k) for k in ('id', 'attempt', 'src')]; s.add_argument('--notes', required=True); s.add_argument('--straight')
    s = c.add_parser('fit'); [s.add_argument(k) for k in ('id', 'src', 'dst', 'working', 'donor')]
    s.add_argument('--overrides'); s.add_argument('--measure-only', action='store_true'); s.add_argument('--donor-review'); s.add_argument('--authority')
    s = c.add_parser('preview'); s.add_argument('id'); s.add_argument('suffix')
    s = c.add_parser('stage'); s.add_argument('id'); s.add_argument('suffix'); s.add_argument('stage')
    s = c.add_parser('review'); [s.add_argument(k) for k in ('id', 'suffix', 'stage')]; s.add_argument('decision', choices=['approved', 'rejected']); s.add_argument('notes')
    s = c.add_parser('chain'); s.add_argument('id'); s.add_argument('suffix'); s.add_argument('stages', nargs='+', choices=PROCESSING)
    s = c.add_parser('batch'); s.add_argument('items', nargs='+', help='ID:SUFFIX')
    s.add_argument('--stages', type=stage_list, required=True, help='comma-separated, e.g. fit,reduce,unwrap')
    s.add_argument('--jobs', type=int, default=2)
    s = c.add_parser('fixture-inputs'); s.add_argument('id'); s.add_argument('suffix', help='a manifest of the design (its family contract)'); s.add_argument('name')
    s = c.add_parser('refixture'); [s.add_argument(k) for k in ('id', 'suffix', 'name')]; s.add_argument('--capture', action='store_true')
    s = c.add_parser('capture'); s.add_argument('fixture'); s.add_argument('output')
    s = c.add_parser('contract'); s.add_argument('family'); s.add_argument('id'); s.add_argument('--wave', required=True); s.add_argument('--visible', type=int)
    s = c.add_parser('views'); s.add_argument('glb'); s.add_argument('output'); s.add_argument('--textured', action='store_true')
    s = c.add_parser('decimate'); s.add_argument('source'); s.add_argument('target'); s.add_argument('--faces', type=int, help='default: the 40,000-triangle working shell')
    a = p.parse_args(argv); d = Driver(Workspace.load(a.workspace))
    result = {
        'comfy': lambda: d.comfy(a.action), 'image': lambda: d.image(a.design, a.kind), 'condition': lambda: d.condition(a.design, a.id, a.source, a.notes, a.keyed),
        'gen': lambda: d.gen(a.id, a.stage, a.manifest, a.attempt), 'calibrated': lambda: d.calibrated(a.id, a.fov, a.source),
        'approve-geometry': lambda: d.approve_geometry(a.id, a.attempt, a.src, a.dst, a.notes),
        'textured': lambda: d.textured(a.id, a.attempt, a.src, a.notes, a.straight),
        'fit': lambda: d.fit(a.id, a.src, a.dst, a.working, a.donor, a.overrides, measure_only=a.measure_only, donor_review=a.donor_review, authority=a.authority),
        'preview': lambda: d.preview(a.id, a.suffix), 'stage': lambda: d.stage(a.id, a.suffix, a.stage),
        'review': lambda: d.review(a.id, a.suffix, a.stage, a.decision, a.notes), 'chain': lambda: d.chain(a.id, a.suffix, a.stages),
        'batch': lambda: d.batch(a.items, a.stages, a.jobs), 'fixture-inputs': lambda: d.fixture_inputs(a.id, a.suffix, a.name),
        'refixture': lambda: d.refixture(a.id, a.suffix, a.name, a.capture), 'capture': lambda: d.capture(a.fixture, a.output),
        'contract': lambda: d.contract(a.family, a.id, a.wave, a.visible), 'views': lambda: d.views(a.glb, a.output, a.textured),
        'decimate': lambda: d.decimate(a.source, a.target, a.faces),
    }[a.command]()
    print(json.dumps(result, indent=1, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
