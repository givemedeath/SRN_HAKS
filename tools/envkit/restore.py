"""The generated sources of a game set's models, copied out of an archive of a retired worktree.

A model's source folder (its `model.glb` and maps) stays in ignored output, and goes into an archive with the worktree
that made it. Converting such a model again (a changed halo rule, a retouch) needs the folder back whole: `shape`
reads the colour map alone, `game` and `tiles` every map, and a folder restored for a look at the shape fails the
conversion at its first missing map (the older sets' props, 2026-11-15). An archive is only read; the copies go into a
folder of the caller's and are checked against the archive's own hashes."""
import hashlib
import json
import shutil
from pathlib import Path

from . import require


def sources(archive, output, models, names):
    """Copy the source folders of `names` (models of the game set file `models`) from `archive` into `output`, under
    the paths the archive gives them (`output/envkit/<set>/<source>/...`), so that `<output>/output/envkit/<set>` is
    a root for `game`, `tiles` and `view`. An archive is a folder with `archive-manifest.json` ({files: {path:
    {sha256}}, bases: [other archives its objects may lie in]}) and `objects/<first two of the hash>/<hash>`. A file
    already there with the archive's hash is left; one that differs is refused, never written over. Returns {model:
    {source, files, roots}}, `files` those copied now."""
    archive, output = Path(archive).resolve(), Path(output).resolve()
    require((archive / 'archive-manifest.json').is_file(), f'No archive-manifest.json in {archive}')
    require(archive != output and archive not in output.parents, 'An archive is only read: restore into a folder outside it')
    manifest = json.loads((archive / 'archive-manifest.json').read_text(encoding='utf-8')); files = manifest['files']
    stores = [archive / 'objects'] + [(archive / base).resolve() / 'objects' for base in manifest.get('bases', [])]
    stated = json.loads(Path(models).read_text(encoding='utf-8'))['models']; told = {}
    for name in names:
        require(name in stated, 'No such model in the game set: ' + name)
        source = stated[name]['source'].strip('/')
        found = sorted(path for path in files if path.startswith('output/envkit/') and f'/{source}/' in path and '/' not in path.split(f'/{source}/', 1)[1])
        require(found, f'The archive holds no source folder {source} for {name}')
        copied = 0
        for path in found:
            digest = files[path]['sha256']; target = output / path
            if target.is_file():
                require(hashlib.sha256(target.read_bytes()).hexdigest() == digest, f'{target} is there already and is not the archive\'s file')
                continue
            held = next((store / digest[:2] / digest for store in stores if (store / digest[:2] / digest).is_file()), None)
            require(held is not None, f'The archive and its bases hold no object for {path}')
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(held, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                target.unlink(); require(False, f'The archive\'s object for {path} does not match its hash')
            copied += 1
        told[name] = {'source': source, 'files': copied, 'roots': sorted({str(output / path.split(f'/{source}/', 1)[0]) for path in found})}
    return told
