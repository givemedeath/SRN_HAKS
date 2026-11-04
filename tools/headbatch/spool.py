"""Auto-advance spooler. Runs queued stages one head per launch, passes numeric gates by itself, and leaves every visual gate to a reviewer.

  spool/queue/*.json    {"heads": [...], "stages": STAGES[, "approve": STAGE, "notes": TEXT]} launches each head
  spool/approve/*.json  {"heads": [...], "approve": STAGE, "attempts": {head: ATTEMPT}, "next": STAGES, "notes": TEXT} records a review of
                        the attempts named, and launches the next stages. An attempt that is no longer current is refused (RUNBOOK 200)
  spool/reviewed-rows.json  {head: palette rows}: export and later run only on rows reviewed here (RUNBOOK 109, 112)
  spool/review.md, attention.md, log.txt  what waits for a person
  spool/STOP            ends the loop

Numeric gates: unwrap to bake, palette to export when rows equal the reviewed pins, export to native, native to render.
A launch whose own record never arrives goes to attention, never silently past (RUNBOOK 117). Only one spooler runs on a workspace.

Each finished stage gets its review evidence: repair the clay pair and skirt zone, bake the textured views and grid, ownership its
saved atlas, palette the row ramps, and a refused shell selection the shell sheet. A queued repair gets the repair presets first."""
from datetime import datetime
import itertools
import json
from pathlib import Path
import subprocess
import time

import guards
from head_files import current, write_json
from workspace import PYTHON

RUNNER = Path(__file__).with_name('run_headbatch.py')
PACKAGE_PINS = 'Python package file pins'
NECK_CUT_FAILED = 'Neck cut failed'
SKIRT_GAP = .03  # the default of headkit neck_policy
READ_BACK_LIMIT = 1e-6
POLL_SECONDS = 20
RESTART_GRACE_SECONDS = 60
NUMERIC_GATES = {'unwrap', 'palette', 'export', 'native'}
FINISHED = ('ran', 'reused')


def clock():
    return datetime.now().strftime('%H:%M:%S')


class Spool:
    def __init__(self, workspace, starter=None, tool=None, later=None):
        self.workspace = workspace
        self.folder = workspace.spool
        self.sheets = self.folder/'sheets'
        for name in ('queue', 'approve', 'done', 'results', 'sheets'):
            (self.folder/name).mkdir(parents=True, exist_ok=True)
        path = self.folder/'state.json'
        self.state = json.loads(path.read_text()) if path.exists() else {'launches': {}, 'review': {}, 'attention': {}, 'retries': {}}
        self.state.setdefault('taken', {})
        self.starter = starter or self.start_process
        self.tool = tool or self.run_tool
        self.later = later or self.run_later
        self.running = {}
        self.drawing = {}
        self.sheet_numbers = itertools.count()

    def log(self, message):
        line = f'{clock()} {message}'
        try:
            with open(self.folder/'log.txt', 'a', encoding='utf-8') as log:
                log.write(line+'\n')
            print(line, flush=True)
        except (OSError, ValueError):  # a closed console or a held log must not end the loop
            pass

    def review(self, head, stage, text):
        self.state['review'][f'{head}/{stage}'] = {'at': clock(), 'text': text}
        self.log(f'REVIEW {head} {stage}: {text}')

    def attention(self, head, stage, text):
        self.state['attention'][f'{head}/{stage}'] = {'at': clock(), 'text': text}
        self.log(f'ATTENTION {head} {stage}: {text}')

    def guarded(self, head, stage, action):
        """One bad file or head lands in attention, and the rest of the batch keeps moving (RUNBOOK 188)."""
        try:
            return action()
        except Exception as error:
            self.attention(head, stage, f'{type(error).__name__}: {error}'[:300])
            return None

    def save(self):
        write_json(self.folder/'state.json', self.state)

    def start_process(self, name, stages, head, approve, notes):
        command = self.command(['run', name, stages, head, '--result', self.folder/'results'/f'{name}.json'])
        if approve:
            command += ['--approve', approve, f"--notes={notes or ''}"]  # joined: a note can start with a dash
        with open(self.folder/'results'/f'{name}.out', 'w', encoding='utf-8') as out:
            return subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT)

    def command(self, arguments):
        return [PYTHON, '-B', str(RUNNER), '--workspace', str(self.workspace.file or self.workspace.root), *[str(item) for item in arguments]]

    def run_tool(self, *arguments):
        done = subprocess.run(self.command(arguments), capture_output=True, text=True)
        return done.returncode, (done.stdout.strip() or done.stderr.strip()).splitlines()[-1:] or ['']

    def run_later(self, *arguments):
        """Heavy sheets wait for a CPU slot in their own process, so the spooler keeps moving. A sheet that dies goes to attention (RUNBOOK 102)."""
        log = self.sheets/f'{arguments[0]}-{datetime.now():%H%M%S}-{next(self.sheet_numbers)}.log'
        with open(log, 'w', encoding='utf-8') as out:
            self.drawing[log] = subprocess.Popen(self.command(['review', '--slot', *arguments]), stdout=out, stderr=subprocess.STDOUT)

    def draw(self, sheet, *arguments):
        """A reused stage keeps the sheet it already has."""
        if not sheet.exists():
            self.later(*arguments)

    def launch(self, stages, head, approve=None, notes=None):
        name = f"sp-{stages.split(',')[0]}-{head}-{datetime.now():%H%M%S%f}"
        self.log(f"launch {name}: {stages}{f' --approve {approve}' if approve else ''} {head}")
        self.running[name] = self.starter(name, stages, head, approve, notes)
        self.state['launches'][name] = {'started': clock(), 'startedAt': time.time(), 'head': head, 'approve': approve}
        self.save()  # a launch the state does not name would be lost to a restart
        return name

    def receipt(self, head, stage, folder=None):
        """The attempt batch reported, or else the newest with a receipt: a reused stage can have a newer failed attempt beside it (RUNBOOK 188)."""
        if folder:
            return Path(folder).name, guards.read(Path(folder)/'receipt.json')
        found = guards.attempts(self.workspace.head(head), stage)
        for attempt in reversed(found):
            if (attempt/'receipt.json').exists():
                return attempt.name, guards.read(attempt/'receipt.json')
        return None, {}

    def on_failure(self, head, stage, item):
        attempt, receipt = self.receipt(head, stage)
        if item.get('error') and not item.get('attempt'):  # refused before an attempt began: the newest receipt is an older failure
            attempt, receipt = 'before any attempt', {'error': item['error']}
        error = str(item.get('error') or receipt.get('error', ''))
        retries = self.state['retries']
        if PACKAGE_PINS in error and not retries.get(f'{head}/{stage}'):  # a foreign .pyc, cleaned by the next launch's guard (RUNBOOK 90)
            retries[f'{head}/{stage}'] = 1
            self.log(f'{head} {stage}: package pin failure, relaunching once')
            self.launch(stage, head)
            return
        if stage == 'unwrap' and guards.COVERAGE.search(error):
            _, text = self.tool('presets', head, '--uv-only')  # plans only: a lower floor records a review, which is a person's (RUNBOOK 186)
            self.attention(head, stage, f'{attempt}: {text[0]} | after review: presets {head} --uv-only --apply --review-floor NOTES, then requeue unwrap')
            return
        queued = ''
        if stage == 'repair' and NECK_CUT_FAILED in error and 'shells' in error:  # the cut left several shells; a refusal before the cut has no uncut master, and carries its table in the receipt
            uncut = self.workspace.head(head)/'run'/'repair'/attempt/'master-uncut.glb'
            evidence = self.workspace.head(head)/'review-evidence'
            evidence.mkdir(exist_ok=True)
            if uncut.exists():
                self.later('cutshells', head, uncut, evidence/f'cutshells-{attempt}.json', evidence/f'cutshells-{attempt}.png')
                queued = f' | cutshells queued: {evidence.name}/cutshells-{attempt}.png'
        self.attention(head, stage, f'failed {attempt}: {error[:500] or "no receipt error"}{queued}')

    def on_success(self, head, stage, item):
        attempt, receipt = self.receipt(head, stage, item.get('attempt'))
        result = receipt.get('result', {})
        manifest = guards.read(self.workspace.head(head)/'manifest.json')
        approved = f'spool {clock()[:5]}:'
        if stage == 'repair':
            self.review(head, stage, f'{attempt}: {self.repair_evidence(head, attempt, manifest)}')
        elif stage == 'bake':
            self.later('bakeviews', head, attempt)  # named, because the head can move on while the sheet waits for a slot
            self.review(head, stage, f'{attempt}: bakeviews queued: {head}/review-evidence/bake-tex.png, bake-grid.png')
        elif stage == 'ownership':
            sheet = self.sheets/f'{head}-ownership-{attempt}.png'
            self.draw(sheet, 'ownsheet', head, attempt, sheet)  # the saved atlas: a rules preview would miss the face-mask channels
            self.review(head, stage, f'{attempt}: ownership sheet queued: {sheet}')
        elif stage == 'unwrap':
            passed, text = guards.unwrap_gates(result)
            if passed:
                self.launch('bake', head, 'unwrap', f'{approved} unwrap gates passed, {text}')
            else:
                self.attention(head, stage, f'{attempt}: {text}')
        elif stage == 'palette':
            rows = {key: value for key, value in result.get('rows', {}).items() if key in manifest['palette'].get('rows', {})}
            code, text = self.tool('review', 'rowramps', head)
            sheet = f'ROWRAMPS FAILED: {text[0]}' if code else f'sheet {head}/review-evidence/rowramps.png'
            if code:
                self.attention(head, stage, sheet)
            if rows == manifest['palette'].get('rows', {}) and guards.rows_reviewed(self.workspace, head):
                self.launch('export', head, 'palette', f'{approved} every palette row equals its reviewed pin {rows}')
            else:
                self.review(head, stage, f'{attempt}: rows {rows} | {sheet}')
        elif stage == 'export':
            matrix = guards.fit_matrix(self.workspace.head(head))
            budget = manifest['mesh'].get('triangleBudget', 20000)
            text = f"{result.get('model')} {result.get('triangles')} tri, matrix {'= reviewed fit' if result.get('matrix') == matrix else 'DIFFERS from the reviewed fit'}"
            if result.get('matrix') == matrix and 0 < result.get('triangles', 0) <= budget and result.get('plt', {}).get('sha256'):
                self.launch('native', head, 'export', f'{approved} export {text}, PLT bound')
            else:
                self.review(head, stage, f'{attempt}: {text}')
        elif stage == 'native':
            errors = [result.get(key, 1) for key in ('positionsMaximumError', 'normalsMaximumError', 'uvMaximumError')]
            text = f"{result.get('model')} read-back errors {errors}"
            if result.get('onlyFixedStringFieldsChanged') and max(errors) < READ_BACK_LIMIT:
                self.launch('render', head, 'native', f'{approved} native {text}, only fixed string fields changed')
            else:
                self.review(head, stage, f'{attempt}: {text}')
        else:
            self.review(head, stage, f'{attempt}: ran')

    def repair_evidence(self, head, attempt, manifest):
        folder = self.workspace.head(head)/'run'/'repair'/attempt
        try:
            jaw = guards.jaw(self.workspace.head(head), self.workspace.landmarks(), attempt)
        except guards.Refused as refusal:
            jaw = f'JAW FAIL - {refusal}'
        sheet = self.sheets/f'{head}-repair-{attempt}.png'
        matrix = self.sheets/f'{head}-fit-matrix.json'
        matrix.write_text(json.dumps(guards.fit_matrix(self.workspace.head(head))), encoding='utf-8')
        self.draw(sheet, 'clay', sheet, f"uncut={folder/'master-uncut.glb'}", f"final={folder/'final.glb'}", '--matrix', matrix, '--views', 'back,left,bottom', '--size', '360')  # without the matrix "back" shows the face
        text = f'{jaw} | sheet queued: {sheet}'
        skirt = manifest['mesh'].get('neck', {}).get('cut', {}).get('skirt')
        if skirt is not None:  # the skirt's hair zone at its gap beside 3 cm, so a kept generated neck shows (RUNBOOK 113)
            zone = self.sheets/f'{head}-skirtzone-{attempt}.png'
            self.draw(zone, 'skirtzone', head, attempt, zone, *sorted({skirt.get('gap', SKIRT_GAP), SKIRT_GAP}))
            text += f' | skirt zone {zone}'
        return text

    def handle(self, name, data, approved=None):
        if data.get('refused') or data.get('error'):
            self.attention(name, 'launch', str(data.get('refused') or data.get('error'))[-300:])  # the reason ends a launcher's stderr
            return
        if not data.get('heads'):
            self.attention(name, 'launch', f"a launch finished with no stage result (RUNBOOK 117): see {data.get('errors')}")
            return
        for row in data['heads']:
            self.handle_row(name, row, approved)

    def handle_row(self, name, row, approved):
        head, stages = row['id'], row['stages']
        if row.get('error'):  # a refused approval: nothing ran, and the stage stays open with the reason (RUNBOOK 188)
            self.attention(head, approved or 'launch', f"{row['error'][:300]} in {name}")
            return
        if approved:
            self.state['review'].pop(f'{head}/{approved}', None)
            self.state['attention'].pop(f'{head}/{approved}', None)
        if all(item['status'] == 'skipped' for item in stages):
            self.attention(head, 'launch', f'nothing ran in {name} (RUNBOOK 117)')
            return
        ran = False
        for index, item in enumerate(stages):
            stage, status = item['stage'], item['status']
            if status in FINISHED:  # an earlier valid result stands; review it like a fresh one
                self.state['attention'].pop(f'{head}/{stage}', None)  # a requeue that worked answers the failure that asked for it
                went_on = any(later['status'] in (*FINISHED, 'failed') for later in stages[index+1:])
                if not (went_on and stage in NUMERIC_GATES):  # the chain is already past this gate: passing it again would launch the next stage twice
                    self.on_success(head, stage, item)
                ran = True
            elif status == 'failed':
                self.on_failure(head, stage, item)
                ran = False
            elif status.startswith('blocked') and not ran:
                self.attention(head, stage, f"{status} in {name}: {item.get('reason', '')}"[:500])

    def launch_alive(self, name, info):
        """A launch from before a restart has no process here: the lock on its head shows it is still going, once it has had time to take it."""
        process = self.running.get(name)
        if process is not None:
            return process.poll() is None
        return time.time()-info['startedAt'] < RESTART_GRACE_SECONDS or guards.head_busy(self.workspace, info['head'])

    def scan_launches(self):
        for name, info in list(self.state['launches'].items()):
            path = self.folder/'results'/f'{name}.json'
            if path.exists() or not self.launch_alive(name, info):
                del self.state['launches'][name]
                self.running.pop(name, None)
                if path.exists():
                    self.guarded(name, 'launch', lambda: self.handle(name, guards.read(path), info.get('approve')))
                else:
                    self.attention(name, 'launch', 'the launch ended without a result: see its .out file (RUNBOOK 117)')

    def scan_sheets(self):
        for log, process in list(self.drawing.items()):
            code = process.poll()
            if code is not None:
                del self.drawing[log]
                if code:
                    self.attention(log.stem, 'sheet', f'exit {code}: see {log}')

    def taken(self, path):
        """The heads a request file has already launched or refused: it can outlive a pass, edited or held open, and none of them must fire twice (RUNBOOK 207)."""
        return self.state['taken'].setdefault(f'{path.parent.name}/{path.name}', [])

    def retire(self, path):
        path.rename(self.folder/'done'/f'{datetime.now():%H%M%S%f}-{path.parent.name}-{path.name}')  # approve/a.json and queue/a.json can retire in one clock tick
        self.state['taken'].pop(f'{path.parent.name}/{path.name}', None)

    def scan_requests(self):
        waiting = {f'{path.parent.name}/{path.name}' for name in ('approve', 'queue') for path in (self.folder/name).glob('*.json')}
        self.state['taken'] = {key: heads for key, heads in self.state['taken'].items() if key in waiting}  # withdrawn files
        self.scan_approvals()
        self.scan_queue()

    def scan_approvals(self):
        for path in sorted((self.folder/'approve').glob('*.json')):
            self.guarded(path.name, 'approve', lambda: self.take_approval(path))
            self.guarded(path.name, 'approve', lambda: self.retire(path))

    def take_approval(self, path):
        request = guards.read(path)
        taken = self.taken(path)
        for head in request['heads']:
            if head not in taken:
                self.guarded(head, request['approve'], lambda: self.approve_head(head, request))
                taken.append(head)

    def approve_head(self, head, request):
        """The review stays open until its launch records the approval: headkit can still refuse it (RUNBOOK 188). Headkit binds an approval to the
        stage's current attempt, so the attempt the reviewer saw must still be that one (RUNBOOK 200)."""
        stage, seen = request['approve'], request.get('attempts', {}).get(head)
        now = current(self.workspace.head(head), stage)
        if seen is None:
            raise guards.Refused(f'{head}: name the attempt reviewed in "attempts"; {stage} is at {now}')
        if seen != now:
            raise guards.Refused(f'{head}: {seen} of {stage} was reviewed, but the current attempt is {now}: review that one')
        if not request.get('next'):
            raise guards.Refused(f'{head}: an approval records through its next launch, so give "next"; a last stage needs a headkit review')
        if stage == 'repair':
            guards.jaw(self.workspace.head(head), self.workspace.landmarks())
        if 'repair' not in request['next'].split(',') or self.repair_presets(head):
            self.launch(request['next'], head, stage, request.get('notes'))

    def scan_queue(self):
        for path in sorted((self.folder/'queue').glob('*.json')):
            changed = self.guarded(path.name, 'queue', lambda: self.take_queue(path))
            if path.exists() and not changed:
                self.guarded(path.name, 'queue', lambda: self.retire(path))

    def take_queue(self, path):
        """True when the file changed under it: it stays queued, to be read afresh on the next pass."""
        raw = path.read_bytes()
        request = guards.read(path)
        taken = self.taken(path)
        for head in request['heads']:
            if head in taken:
                continue
            if self.guarded(head, request['stages'].split(',')[0], lambda: self.queue_head(path, raw, head, request)):
                return True
            taken.append(head)
            self.guarded('spool', 'scan_launches', self.scan_launches)  # presets take up to a minute a head, and a finished launch should not idle its slot for them
        return False

    def repair_presets(self, head):
        code, text = self.tool('presets', head, '--apply')
        self.log(f'preset {text[0]}')
        if code:
            self.attention(head, 'repair', f'presets: {text[0]}')
        return not code

    def queue_head(self, path, raw, head, request):
        stages = request['stages']
        if 'repair' in stages.split(',') and not self.repair_presets(head):
            return False
        if not path.exists() or path.read_bytes() != raw:  # the check follows the presets, which take seconds: withdrawn or edited in that time (RUNBOOK 114)
            self.log(f'{path.name} changed before launch: {head} skipped')
            return True
        self.launch(stages, head, request.get('approve'), request.get('notes'))
        return False

    def report(self):
        def rows(entries):
            return '\n'.join(f"- {key}: {value['text']} ({value['at']})" for key, value in sorted(entries.items())) or '- none'
        (self.folder/'review.md').write_text(f"# Awaiting review ({clock()})\n{rows(self.state['review'])}\n", encoding='utf-8', newline='\n')
        (self.folder/'attention.md').write_text(f"# Needs a decision ({clock()})\n{rows(self.state['attention'])}\n", encoding='utf-8', newline='\n')
        self.save()

    def step(self):
        for scan in (self.scan_launches, self.scan_sheets, self.scan_requests):
            self.guarded('spool', scan.__name__, scan)
        self.guarded('spool', 'report', self.report)  # a reader holding one of its files must not end the loop; the next pass writes it again

    def wait(self):
        """Up to POLL_SECONDS, ending when a launch finishes, so a numeric gate advances without idling a slot."""
        for _ in range(POLL_SECONDS):
            time.sleep(1)
            if any(process.poll() is not None for process in self.running.values()):
                return

    def loop(self, once=False):
        with guards.only_spooler(self.workspace):
            self.log('spool start')
            while not (self.folder/'STOP').exists():
                self.step()
                if once:
                    break
                self.wait()
            self.log('spool stop')
