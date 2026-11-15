"""The itemkit workspace: one workspace.json holding every machine path the item driver needs.

Relative paths in the file resolve against its folder. Nothing under tools/itemkit names a machine path; the
repository root comes from this file's location. Load order: an explicit path, then $SRN_ITEM_WORKSPACE, then
output/itemkit/workspace.json in this checkout (ignored by git). See workspace.example.json.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENVIRONMENT = 'SRN_ITEM_WORKSPACE'
# Joined from parts: tools/test_impact.py resolves a whole path literal against files on disk, and this one is ignored
# local state, so it would put a machine-only edge into the committed catalog.
DEFAULT = REPO/'output'/'itemkit'/'workspace.json'
REQUIRED = ('python', 'pythonPath', 'blender', 'runtime', 'bindings', 'handoff', 'items')


class WorkspaceError(ValueError):
    pass


@dataclass(frozen=True)
class Workspace:
    root: Path
    data: dict
    file: Path

    @classmethod
    def load(cls, path=None):
        chosen = Path(path or os.environ.get(ENVIRONMENT) or DEFAULT).resolve()
        if chosen.is_dir(): chosen = chosen/'workspace.json'
        try: data = json.loads(chosen.read_text(encoding='utf-8-sig'))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkspaceError(f'Cannot read item workspace {chosen}: {error} (see tools/itemkit/workspace.example.json)') from error
        if data.get('kind') != 'srn-item-workspace' or data.get('schemaVersion') != 1:
            raise WorkspaceError(f'{chosen} is not a schema 1 srn-item-workspace')
        missing = [key for key in REQUIRED if key not in data]
        if missing: raise WorkspaceError(f'{chosen} is missing {missing}')
        return cls(chosen.parent, data, chosen)

    def path(self, value):
        return Path(value) if Path(value).is_absolute() else (self.root/value).resolve()

    def setting(self, *keys):
        """A nested path setting, or None when this workspace does not have it."""
        value = self.data
        for key in keys:
            if not isinstance(value, dict) or key not in value: return None
            value = value[key]
        return self.path(value) if value else None

    @property
    def python(self): return self.path(self.data['python'])
    @property
    def blender(self): return self.path(self.data['blender'])
    @property
    def runtime(self): return self.path(self.data['runtime'])
    @property
    def handoff(self): return self.path(self.data['handoff'])
    @property
    def items(self): return self.path(self.data['items'])

    def bindings(self, kind='processing'):
        """Processing bindings by default; 'generation' for the GPU stages when the workspace keeps them apart."""
        key = 'generationBindings' if kind == 'generation' and self.data.get('generationBindings') else 'bindings'
        return self.runtime/self.data[key]

    @property
    def hash_cache(self):
        """The launcher's opt-in stat-keyed digest cache (tools/phenotypes/launch_hash_cache.py), local machine state.
        `"hashCache": false` in the workspace turns it off: every launch then hashes every input in full."""
        value = self.data.get('hashCache', 'launch-hash-cache/cache.sqlite')
        return self.path(value) if value else None

    def environment(self):
        env = dict(os.environ); env['PYTHONPATH'] = os.pathsep.join([*(str(self.path(p)) for p in self.data['pythonPath']), str(REPO)])
        # As headbatch does: a launch freezes thousands of tool files before and after its run, and so does every
        # Blender worker launch inside a stage. A caller's own setting wins.
        if self.hash_cache: env.setdefault('SRN_LAUNCH_HASH_CACHE', str(self.hash_cache))
        return env
