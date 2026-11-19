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


def _newest_first(folder, pattern='*.npz'):
    """The kept files of a folder, the newest first. One that another build takes away while they are listed is left
    out: its `stat` failed and stopped a build whose own arrays were already kept (review of PR 175, 2026-11-18)."""
    aged = []
    for path in folder.glob(pattern):
        try:
            aged.append((path.stat().st_mtime, path))
        except OSError:
            continue
    return [path for _, path in sorted(aged, key=lambda one: one[0], reverse=True)]


def _gone(path):
    """Take a file away, if it can be: one open in another build stays, and goes at the next tidying."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def keep(kept, write):
    """Keep a file as `kept`: `write(staged)` fills an open file of this call's own beside it, which is then renamed.
    Two builds that kept the same thing at once shared a staging file, and the second found it already renamed
    (review of PR 175, 2026-11-18); the staging file has another suffix, so no tidying takes another's. Where the
    kept file cannot be written (another build holds it open, the disk is full) nothing is kept and nothing stops:
    what was made is the caller's already."""
    import uuid
    kept.parent.mkdir(parents=True, exist_ok=True); part = kept.with_name(f'{kept.stem}.{uuid.uuid4().hex}.part')
    try:
        with open(part, 'wb') as staged:
            write(staged)
        part.replace(kept)
    except OSError:
        pass
    finally:
        _gone(part)


def used(kept):
    """Mark a kept file as read now, so the tidying keeps it; one taken away meanwhile was read all the same."""
    try:
        os.utime(kept)
    except OSError:
        pass


def tidy(folder, most, pattern='*.npz'):
    """Take away all but the `most` newest kept files of a folder."""
    for old in _newest_first(folder, pattern)[most:]:
        _gone(old)


def arrays(kind, made_from, make, *, faces):
    """`make()`'s tuple of arrays, read back if it was kept for the same `made_from` (`key`), else made and kept
    (`keep`). `faces` is the model's size: under LEAST nothing is kept."""
    if off() or faces < LEAST:
        return make()
    folder = ROOT / kind; kept = folder / (key(*made_from) + '.npz')
    if kept.is_file():
        try:
            with np.load(kept) as held:
                found = tuple(held[f'a{index}'] for index in range(len(held.files)))
        except Exception:  # half written by a build that was stopped, or taken away by another: made again
            _gone(kept)
        else:
            used(kept); return found
    made = tuple(make())
    keep(kept, lambda staged: np.savez(staged, **{f'a{index}': np.asarray(one) for index, one in enumerate(made)}))  # a file, not a name: `savez` would add `.npz` to the name
    tidy(folder, KEPT)
    return made
