"""The external tools armorkit runs, resolved from the shared tool root and checked against the lock.

cleanmodels compiles armorkit parts offline and makes the race versions that pass review (docs/armorkit/plan.md,
revision "cleanmodels 4.17.5 adopted"). It is the standalone build pinned in tools/shared-tools.lock.json, not
the cleanmodels port inside the Neverblender add-on that the other kits compile with.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLEANMODELS = 'cleanmodels'


def cleanmodels(*, root=None, repo=REPO):
    """The pinned cleanmodels executable: path, version and verified SHA-256 (see shared_tools.resolve_tool).

    Both arguments are keyword-only, because shared_tools.resolve_tool takes them in the other order.
    `root` overrides the shared tool root. A missing or changed executable raises ValueError. Every call
    reads and hashes the executable, so resolve it once per run and pass the result on."""
    from tools import shared_tools
    return shared_tools.resolve_tool(CLEANMODELS, repo, root)
