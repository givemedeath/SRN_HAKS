"""The batch workspace: one folder outside the repository whose workspace.json holds every machine path a batch needs.

Relative paths in the file resolve against its folder, so a workspace can move or be rebuilt on another machine.
Nothing under tools/headbatch names a machine path: the repository root comes from this file's location and the
interpreter from sys.executable."""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO/'tools'
RACE_DATA = json.loads(Path(__file__).with_name('races.json').read_text(encoding='utf-8'))
REQUIRED = ('toolchain', 'migrationReceipt', 'headBindings', 'slots')
ENVIRONMENT = 'SRN_HEAD_WORKSPACE'
RAM_GATES = {1: 6, 2: 8, 3: 10, 4: 13, 5: 16, 6: 16}  # slot: free GB it needs to start a job (user 2026-10-28, race-heads-v1 tracking)


class WorkspaceError(ValueError):
    pass


def prefix(race, sex):
    return f"p{sex[0]}{RACE_DATA['races'][race]['letter']}0"


@dataclass(frozen=True)
class Workspace:
    root: Path
    data: dict
    file: Path = None  # any file load accepted, which child processes must load too

    @classmethod
    def load(cls, path=None):
        chosen = path or os.environ.get(ENVIRONMENT)
        if not chosen:
            raise WorkspaceError(f'Give --workspace or set {ENVIRONMENT} to a workspace.json (see tools/headbatch/workspace.example.json)')
        path = Path(chosen).resolve()
        if path.is_dir():
            path = path/'workspace.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
        except OSError as error:
            raise WorkspaceError(f'Cannot read workspace {path}: {error}') from error
        if data.get('kind') != 'srn-head-workspace' or data.get('schemaVersion') != 1:
            raise WorkspaceError(f'{path} is not a schema 1 srn-head-workspace')
        missing = [key for key in REQUIRED if key not in data]
        if missing:
            raise WorkspaceError(f'{path} is missing {missing}')
        return cls(path.parent, data, path)

    def path(self, value):
        """A workspace path: absolute as written, otherwise relative to the workspace folder."""
        return Path(value) if Path(value).is_absolute() else self.root/value

    def setting(self, key):
        """A path setting, or None when this workspace does not use it."""
        return self.path(self.data[key]) if self.data.get(key) else None

    def require(self, key):
        found = self.setting(key)
        if found is None:
            raise WorkspaceError(f'This step needs "{key}" in workspace.json')
        return found

    @property
    def heads(self):
        return self.path(self.data.get('headsDirectory', 'heads'))

    @property
    def launches(self):
        return self.root/'launches'

    @property
    def locks(self):
        return self.root/'locks'

    @property
    def spool(self):
        return self.root/'spool'

    @property
    def hash_cache(self):
        return self.path(self.data.get('hashCache', 'launch-hash-cache/cache.sqlite'))

    def head(self, name):
        return self.heads/name

    def cpu_slots(self):
        """Read on every attempt, so a cpu-slots file can change the limit while launches wait."""
        try:
            raw = (self.root/'cpu-slots').read_bytes()  # Windows PowerShell's echo writes UTF-16 and its Set-Content a BOM
            value = int(raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig').strip())
        except (OSError, ValueError):
            value = int(self.data.get('cpuSlots', 2))
        return value if 1 <= value <= 6 else 2

    def ram_gates(self):
        """Every slot has a floor; workspace gates may raise, never remove it."""
        gates=dict(RAM_GATES)
        for slot, value in self.data.get('ramGates', {}).items():
            number=int(slot)
            if number not in gates or type(value) not in (int,float) or not math.isfinite(value) or value<gates[number]:
                raise WorkspaceError('ramGates must preserve finite per-slot minimums '+str(RAM_GATES))
            gates[number]=value
        return gates

    def head_ids(self):
        """{head id: (race, sex, slot resref)}; slots lists read as human-male: [84, 85] give human-male-a, human-male-b."""
        out = {}
        for key, numbers in self.data['slots'].items():
            race, sex = key.split('-')
            for letter, number in zip('abcdefghijklmnopqrstuvwxyz', numbers):
                out[f'{key}-{letter}'] = (race, sex, f'{prefix(race, sex)}_head{number:03d}')
        return out

    def fit_reference(self, race, sex):
        name = prefix(race, sex)
        override = self.data.get('fitReferenceOverrides', {}).get(name)
        if override:
            return self.path(override)
        compact = RACE_DATA['compactFitHead'].get(name)
        if compact is None:
            raise WorkspaceError(f'{name} has no stock fit head: set fitReferenceOverrides.{name} in workspace.json')
        return self.require('fitReferences')/f'{name}_head{compact:03d}.mdl'

    def body_neck(self, race, sex):
        return self.require('bodyNecks')/f'{prefix(race, sex)}-neck001-ref.json'

    def landmarks(self):
        """None until the file exists: it is written from precluster output, so a new batch runs before it can have one."""
        path = self.setting('landmarks')
        return json.loads(path.read_text(encoding='utf-8-sig')) if path and path.exists() else None

    def design_reference(self, race, sex):
        reference = self.data.get('designReferences', {}).get(race, {}).get(sex)
        return self.path(reference) if reference else None

    def package_paths(self):
        """The bound Python packages and libraries, in binding order."""
        bindings = json.loads(self.path(self.data['headBindings']).read_text(encoding='utf-8-sig'))
        found = [bindings['pythonPackages']['directory']]
        for library in bindings.get('libraries', {}).values():
            directory = library.get('directory') if isinstance(library, dict) else None
            if directory and directory not in found:
                found.append(directory)
        return found

    def tools_root(self):
        """The shared tools root: the workspace's `toolsRoot`, else SRN_TOOLS_ROOT, else the primary checkout's .tools."""
        if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))
        from shared_tools import tools_root
        return tools_root(REPO, self.data.get('toolsRoot'))[0]

    def python_environment(self, *, packages=False, tools=False):
        """Launches inherit no PYTHONPATH: Blender stages would import the caller's numpy (RUNBOOK 107)."""
        environment = {key: value for key, value in os.environ.items() if key != 'PYTHONPATH'}
        environment.update(PYTHONDONTWRITEBYTECODE='1', SRN_LAUNCH_HASH_CACHE=str(self.hash_cache))
        if self.data.get('toolsRoot'):
            # The workspace's own tools root, resolved as the launcher resolves it: its children then take the same
            # GPU lease and read the same shared ComfyUI registry (headkit.shared_comfy) as the launch that holds it.
            # (shared_tools.tools_root resolves an explicit root exactly so, then checks it; the launcher checks it.)
            environment['SRN_TOOLS_ROOT'] = str(Path(self.data['toolsRoot']).expanduser().resolve())
        path = ([str(TOOLS)] if tools else [])+(self.package_paths() if packages else [])
        if path:
            environment['PYTHONPATH'] = os.pathsep.join(path)
        return environment


PYTHON = sys.executable
