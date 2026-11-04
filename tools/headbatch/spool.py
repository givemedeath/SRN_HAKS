"""Auto-advance spooler. Runs queued stages one head per launch, passes numeric gates by itself, and leaves every visual gate to a reviewer.

  spool/queue/*.json    {"heads": [...], "stages": STAGES[, "approve": STAGE, "notes": TEXT]} launches each head
  spool/approve/*.json  {"heads": [...], "approve": STAGE, "next": STAGES, "notes": TEXT} records a review and launches the next stages
  spool/reviewed-rows.json  {head: palette rows}: export and later run only on rows reviewed here (RUNBOOK 109, 112)
  spool/review.md, attention.md, log.txt  what waits for a person
  spool/STOP            ends the loop

Numeric gates: unwrap to bake, palette to export when rows equal the reviewed pins, export to native, native to render.
A launch whose own record never arrives goes to attention, never silently past (RUNBOOK 117).

Each finished stage gets its review evidence: repair the clay pair and skirt zone, bake the textured views and grid, ownership the
rule sheet, palette the row ramps, and a failed shell selection the shell sheet. A queued repair gets the repair presets first."""
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import time

import guards
from workspace import PYTHON

RUNNER = Path(__file__).with_name('run_headbatch.py')
COVERAGE = re.compile(r'Insufficient useful UV coverage \(([.\d]+) at 2K')
PACKAGE_PINS = 'Python package file pins'
DELETED_SHELLS = 'Deleted shells cover'
SKIRT_GAP = .015
WIDE_SKIRT_GAP = .03
READ_BACK_LIMIT = 1e-6
POLL_SECONDS = 20
STAGE_GATED_ON_ROWS = {'export', 'native', 'render'}


def clock():
    return datetime.now().strftime('%H:%M:%S')


class Spool:
    def __init__(self, workspace, starter=None, tool=None, later=None):
        self.workspace = workspace
        self.folder = workspace.spool
        for name in ('queue', 'approve', 'done', 'results'):
            (self.folder/name).mkdir(parents=True, exist_ok=True)
        path = self.folder/'state.json'
        self.state = json.loads(path.read_text()) if path.exists() else {'launches': {}, 'review': {}, 'attention': {}, 'retries': {}}
        self.starter = starter or self.start_process
        self.tool = tool or self.run_tool
        self.later = later or self.run_later
        self.running = {}

    def log(self, message):
        line = f'{clock()} {message}'
        print(line, flush=True)
        with open(self.folder/'log.txt', 'a', encoding='utf-8') as log:
            log.write(line+'\n')

    def review(self, head, stage, text):
        self.state['review'][f'{head}/{stage}'] = {'at': clock(), 'text': text}
        self.log(f'REVIEW {head} {stage}: {text}')

    def attention(self, head, stage, text):
        self.state['attention'][f'{head}/{stage}'] = {'at': clock(), 'text': text}
        self.log(f'ATTENTION {head} {stage}: {text}')

    def start_process(self, name, stages, head, approve, notes):
        command = [PYTHON, '-B', str(RUNNER), '--workspace', str(self.workspace.root), 'run', name, stages, head, '--result', str(self.folder/'results'/f'{name}.json')]
        if approve:
            command += ['--approve', approve, '--notes', notes or '']
        with open(self.folder/'results'/f'{name}.out', 'w', encoding='utf-8') as out:
            return subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT)

    def command(self, arguments):
        return [PYTHON, '-B', str(RUNNER), '--workspace', str(self.workspace.root), *[str(item) for item in arguments]]

    def run_tool(self, *arguments):
        done = subprocess.run(self.command(arguments), capture_output=True, text=True)
        return done.returncode, (done.stdout.strip() or done.stderr.strip()).splitlines()[-1:] or ['']

    def run_later(self, *arguments):
        """Heavy sheets wait for a CPU slot in their own process, so the spooler keeps moving."""
        subprocess.Popen(self.command(['review', '--slot', *arguments]), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def sheets(self):
        folder = self.folder/'sheets'
        folder.mkdir(exist_ok=True)
        return folder

    def launch(self, stages, head, approve=None, notes=None):
        name = f"sp-{stages.split(',')[0]}-{head}-{datetime.now():%H%M%S%f}"
        self.log(f"launch {name}: {stages}{f' --approve {approve}' if approve else ''} {head}")
        self.running[name] = self.starter(name, stages, head, approve, notes)
        self.state['launches'][name] = {'done': False, 'started': clock(), 'head': head}
        return name

    def receipt(self, head, stage):
        found = guards.attempts(self.workspace.head(head), stage)
        for attempt in reversed(found):
            if (attempt/'receipt.json').exists():
                return attempt.name, guards.read(attempt/'receipt.json')
        return None, {}

    def rows_unreviewed(self, head, stages):
        if not set(stages.split(',')) & STAGE_GATED_ON_ROWS:
            return False
        return not self.rows_reviewed(head)

    def rows_reviewed(self, head):
        path = self.folder/'reviewed-rows.json'
        pins = guards.read(self.workspace.head(head)/'manifest.json')['palette'].get('rows', {})
        return path.exists() and guards.read(path).get(head) == pins

    def on_failure(self, head, stage, status):
        attempt, receipt = self.receipt(head, stage)
        error = str(receipt.get('error', ''))[:500]
        retries = self.state['retries']
        if PACKAGE_PINS in error and not retries.get(f'{head}/{stage}'):  # a foreign .pyc, cleaned by the next launch's guard (RUNBOOK 90)
            retries[f'{head}/{stage}'] = 1
            self.log(f'{head} {stage}: package pin failure, relaunching once')
            self.launch(stage, head)
            return
        if stage == 'unwrap' and COVERAGE.search(error):
            code, text = self.tool('presets', head, '--uv-only', '--apply')
            if code == 0:
                self.log(f'{head} unwrap: {text[0]}')
                self.launch('unwrap', head)
            else:
                self.attention(head, stage, f'{attempt}: {text[0]}')
            return
        if stage == 'repair' and DELETED_SHELLS in error:
            uncut = self.workspace.head(head)/'run'/'repair'/attempt/'master-uncut.glb'
            evidence = self.workspace.head(head)/'review-evidence'
            evidence.mkdir(exist_ok=True)
            if uncut.exists():
                self.later('cutshells', head, uncut, evidence/f'cutshells-{attempt}.json', evidence/f'cutshells-{attempt}.png')
                error += f' | cutshells queued: {evidence.name}/cutshells-{attempt}.png'
        self.attention(head, stage, f'{status} {attempt}: {error or "no receipt error"}')

    def on_success(self, head, stage):
        attempt, receipt = self.receipt(head, stage)
        result = receipt.get('result', {})
        manifest = guards.read(self.workspace.head(head)/'manifest.json')
        approved = f'spool {clock()[:5]}:'
        if stage == 'repair':
            self.review(head, stage, f'{attempt}: {self.repair_evidence(head, attempt, manifest)}')
        elif stage == 'bake':
            self.later('bakeviews', head)
            self.review(head, stage, f'{attempt}: bakeviews queued: {head}/review-evidence/bake-tex.png, bake-grid.png')
        elif stage == 'ownership':
            rules = self.sheets()/f'{head}-ownership.json'
            sheet = self.sheets()/f'{head}-ownership-{attempt}.png'
            rules.write_text(json.dumps(manifest['ownership'], indent=1), encoding='utf-8')
            _, text = self.tool('review', 'own_draft', head, rules, sheet)
            self.review(head, stage, f'{attempt}: {text[0]} | sheet {sheet}')
        elif stage == 'unwrap':
            passed, text = guards.unwrap_gates(result)
            if passed:
                self.launch('bake', head, 'unwrap', f'{approved} unwrap gates passed, {text}')
            else:
                self.attention(head, stage, f'{attempt}: {text}')
        elif stage == 'palette':
            rows = {key: value for key, value in result.get('rows', {}).items() if key in manifest['palette'].get('rows', {})}
            self.tool('review', 'rowramps', head)
            if rows == manifest['palette'].get('rows', {}) and self.rows_reviewed(head):
                self.launch('export', head, 'palette', f'{approved} every palette row equals its reviewed pin {rows}')
            else:
                self.review(head, stage, f'{attempt}: rows {rows} | sheet {head}/review-evidence/rowramps.png')
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
        landmarks = guards.read(self.workspace.setting('landmarks')) if self.workspace.setting('landmarks') else None
        try:
            guards.jaw(self.workspace.head(head), landmarks)
            jaw = 'jaw OK'
        except guards.Refused as refusal:
            jaw = f'JAW FAIL - {refusal}'
        sheet = self.sheets()/f'{head}-repair-{attempt}.png'
        matrix = self.sheets()/f'{head}-fit-matrix.json'
        matrix.write_text(json.dumps(guards.fit_matrix(self.workspace.head(head))), encoding='utf-8')
        self.tool('review', 'clay', sheet, f"uncut={folder/'master-uncut.glb'}", f"final={folder/'final.glb'}", '--matrix', matrix, '--views', 'back,left,bottom', '--size', '360')  # without the matrix "back" shows the face
        text = f'{jaw} | sheet {sheet}'
        skirt = manifest['mesh'].get('neck', {}).get('cut', {}).get('skirt')
        if skirt is not None:  # the skirt's hair zone at its gap beside 3 cm, so a kept generated neck shows (RUNBOOK 113)
            zone = self.sheets()/f'{head}-skirtzone-{attempt}.png'
            gap = skirt.get('gap', SKIRT_GAP)
            self.tool('review', 'skirtzone', head, attempt, zone, gap, *([] if gap == WIDE_SKIRT_GAP else [WIDE_SKIRT_GAP]))
            text += f' | skirt zone {zone}'
        return text

    def handle(self, name, data):
        if data.get('refused') or data.get('error'):
            self.attention(name, 'launch', str(data.get('refused') or data.get('error'))[:300])
            return
        if not data.get('heads'):
            self.attention(name, 'launch', 'a launch finished with no stage result (RUNBOOK 117)')
            return
        for row in data['heads']:
            ran = False
            for item in row['stages']:
                stage, status = item['stage'], item['status']
                if status in ('ran', 'reused'):  # an earlier valid result stands; review it like a fresh one
                    self.on_success(row['id'], stage)
                    ran = True
                elif status == 'failed':
                    self.on_failure(row['id'], stage, status)
                    ran = False
                elif status.startswith('blocked') and not ran:
                    self.attention(row['id'], stage, f'{status} in {name}')

    def scan_launches(self):
        for name, info in list(self.state['launches'].items()):
            if info['done']:
                continue
            path = self.folder/'results'/f'{name}.json'
            process = self.running.get(name)
            if path.exists():
                info['done'] = True
                self.running.pop(name, None)
                self.handle(name, json.loads(path.read_text(encoding='utf-8')))
            elif process is None or process.poll() is not None:
                info['done'] = True
                self.running.pop(name, None)
                self.attention(name, 'launch', 'the launch ended without a result: see its .out file (RUNBOOK 117)')

    def retire(self, path):
        path.rename(self.folder/'done'/f'{datetime.now():%H%M%S%f}-{path.name}')

    def scan_requests(self):
        for path in sorted((self.folder/'approve').glob('*.json')):
            request = guards.read(path)
            landmarks = guards.read(self.workspace.setting('landmarks')) if self.workspace.setting('landmarks') else None
            for head in request['heads']:
                try:
                    if request['approve'] == 'repair':
                        guards.jaw(self.workspace.head(head), landmarks)
                except guards.Refused as refusal:
                    self.attention(head, 'repair', str(refusal))
                    continue
                if self.rows_unreviewed(head, request['next']):
                    self.attention(head, request['next'], 'REFUSED: palette rows are not in reviewed-rows.json (RUNBOOK 112)')
                    continue
                self.launch(request['next'], head, request['approve'], request.get('notes'))
                self.state['review'].pop(f"{head}/{request['approve']}", None)
                self.state['attention'].pop(f"{head}/{request['approve']}", None)
            self.retire(path)
        for path in sorted((self.folder/'queue').glob('*.json')):
            raw = path.read_text(encoding='utf-8')
            request = json.loads(raw)
            for head in request['heads']:
                if not path.exists() or path.read_text(encoding='utf-8') != raw:  # withdrawn or edited while launching (RUNBOOK 114)
                    self.log(f'{path.name} changed before launch: {head} skipped')
                    break
                if 'repair' in request['stages'].split(','):
                    code, text = self.tool('presets', head, '--apply')
                    self.log(f'preset {text[0]}')
                    if code:
                        self.attention(head, 'repair', f'presets: {text[0]}')
                        continue
                if self.rows_unreviewed(head, request['stages']):
                    self.attention(head, request['stages'].split(',')[0], 'REFUSED: palette rows are not in reviewed-rows.json (RUNBOOK 112)')
                    continue
                self.launch(request['stages'], head, request.get('approve'), request.get('notes'))
            if path.exists():
                self.retire(path)

    def report(self):
        def rows(entries):
            return '\n'.join(f"- {key}: {value['text']} ({value['at']})" for key, value in sorted(entries.items())) or '- none'
        (self.folder/'review.md').write_text(f"# Awaiting review ({clock()})\n{rows(self.state['review'])}\n", encoding='utf-8', newline='\n')
        (self.folder/'attention.md').write_text(f"# Needs a decision ({clock()})\n{rows(self.state['attention'])}\n", encoding='utf-8', newline='\n')
        (self.folder/'state.json').write_text(json.dumps(self.state, indent=1), encoding='utf-8', newline='\n')

    def step(self):
        self.scan_launches()
        self.scan_requests()
        self.report()

    def loop(self, once=False):
        self.log('spool start')
        while not (self.folder/'STOP').exists():
            self.step()
            if once:
                break
            time.sleep(POLL_SECONDS)
        self.log('spool stop')
