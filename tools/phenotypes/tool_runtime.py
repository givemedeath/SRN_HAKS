"""Narrow operation-specific tool resolution; no unrelated optional runtimes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_tools import resolve_tool, resolve_runtime, register_run

REPO = Path(__file__).resolve().parents[2]
NAMES = {'nwn_'+name: name for name in ('erf', 'gff', 'tlk', 'resman_cat', 'resman_grep', 'script_comp')}


def tool(name, directory=None, *, path=None, inputs=()):
    key = NAMES.get(name.removesuffix('.exe'), name)
    override = path
    if directory is not None:
        override = Path(directory) / ('nwn_' + key + ('.exe' if sys.platform == 'win32' else ''))
    resolved = resolve_tool(key, REPO, override=override)
    register_run(REPO, tools=[resolved], inputs=inputs)
    return Path(resolved['path'])


def runtime(name, path, *, inputs=()):
    resolved = resolve_runtime(name, path, REPO)
    register_run(REPO, tools=[resolved], inputs=inputs)
    return Path(resolved['path'])


def record_dependencies(pins, *, provenance=()):
    """Register actual consumed paths, reusing the operation's frozen hashes."""
    interpreter=resolve_runtime('blender' if 'bpy' in sys.modules else 'python',sys.executable,REPO)
    return register_run(REPO,tools=[interpreter],
        inputs=[{'path':str(path),'sha256':digest} for path,digest in pins.items()],provenance=provenance)
