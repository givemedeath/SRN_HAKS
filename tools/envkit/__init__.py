"""Environment kit: buildings and props for the FRFZ areas. Nothing is generated on import."""
import contextlib
import shutil
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


@contextlib.contextmanager
def fresh(folder):
    """A folder that appears only when what fills it has finished. The work is done in `<folder>.partial`, which is
    moved into place at the end. A failure leaves the partial folder to be looked at, and the next attempt clears it:
    nothing half done passes for a finished result or stands in the way of the retry."""
    folder = Path(folder); staging = folder.with_name(folder.name + '.partial')
    require(not folder.exists(), 'A fresh folder is required: ' + str(folder))
    shutil.rmtree(staging, ignore_errors=True); staging.mkdir(parents=True)
    yield staging
    staging.rename(folder)
