"""What a build worked out from a model, kept for the next build of the same model.

A tile group is built many times over while its fence, its lit boxes and its path nodes are settled, and most of each
build works out again what the change did not touch: the Shiawase Barrens power station was built seven times on
2026-11-17, each time 84 seconds on the map of its places, 42 on compressing its maps, 28 on squaring it up and 17 on
the winding of its faces, of 197. Each is kept under the hash of everything it was made from, the code that made it
included, in ignored `output/envkit/cache`; ENVKIT_NO_CACHE set works everything out anew and keeps nothing."""
import hashlib
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2] / 'output' / 'envkit' / 'cache'
LEAST = 20000  # faces: a smaller model is worked out faster than it is read back
KEPT = 6  # of a kind: the oldest go


def off():
    return bool(os.environ.get('ENVKIT_NO_CACHE'))


def key(*made_from):
    """The hash of arrays, files (paths: their bytes) and plain values."""
    found = hashlib.sha256()
    for one in made_from:
        if isinstance(one, np.ndarray):
            found.update(repr((one.dtype.str, one.shape)).encode()); found.update(np.ascontiguousarray(one).tobytes())
        elif isinstance(one, Path):
            found.update(one.read_bytes())
        else:
            found.update(repr(one).encode())
    return found.hexdigest()


def arrays(kind, made_from, make, *, faces):
    """`make()`'s tuple of arrays, read back if it was kept for the same `made_from` (`key`), else made and kept.
    `faces` is the model's size: under LEAST nothing is kept."""
    if off() or faces < LEAST:
        return make()
    folder = ROOT / kind; kept = folder / (key(*made_from) + '.npz')
    if kept.is_file():
        try:
            with np.load(kept) as held:
                found = tuple(held[f'a{index}'] for index in range(len(held.files)))
            os.utime(kept); return found
        except Exception:  # half written by a build that was stopped: made again
            kept.unlink(missing_ok=True)
    made = tuple(make()); folder.mkdir(parents=True, exist_ok=True); part = folder / (kept.stem + '.part.npz')
    np.savez(part, **{f'a{index}': np.asarray(one) for index, one in enumerate(made)}); part.replace(kept)
    for old in sorted(folder.glob('*.npz'), key=lambda path: path.stat().st_mtime, reverse=True)[KEPT:]:
        old.unlink(missing_ok=True)
    return made
