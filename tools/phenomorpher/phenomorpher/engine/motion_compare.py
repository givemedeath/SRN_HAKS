"""Compare a published body's effective motion with its library-based replacement chain.

Old: root > private carriers. New: repointed root > shared library > installed a_fa/a_ba chain.
Retained clips must be byte-exact; inherited clips must stay within the approved tolerances.
"""
import json
from pathlib import Path

from .anim_library import (DEFAULT_TOLERANCES, PARENT_FIELD, NativeModel, assembled_drift, chain, clips_equal,
                           compare_clip, digest, effective, release_models, stock_files)


def compare(root, manifest_path, stock_manifest, target, library_path, repointed_path, authorized=(), tolerances=None):
    tolerances = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    root = Path(root).resolve(); manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    stock, stock_paths = stock_files(stock_manifest); old, origins = release_models(root, manifest, stock, stock_paths)
    published = (root/origins[target]['path']).read_bytes(); repointed = Path(repointed_path).read_bytes()
    # Without a library the root names a stock model directly (Human male Large > a_ba).
    library_blob = Path(library_path).read_bytes() if library_path else None
    library = NativeModel(library_blob).decode() if library_blob else None
    a, b = PARENT_FIELD
    if len(published) != len(repointed) or published[:a] != repointed[:a] or published[b:] != repointed[b:]:
        raise ValueError('Repointed root differs outside the supermodel field')
    new = {n: m for n, m in old.items() if origins[n]['origin'] == 'installed-game'}
    new[target] = NativeModel(repointed).decode()
    if library:
        new[library['name']] = library
        if new[target]['parent'] != library['name']:
            raise ValueError('Repointed root does not name the library')
    elif new[target]['parent'] not in new or origins.get(new[target]['parent'], {}).get('origin') != 'installed-game':
        raise ValueError('Repointed root must name the library or an installed stock model')
    old_chain, new_chain = chain(target, old), chain(target, new)
    old_clips, new_clips = effective(old_chain, old), effective(new_chain, new)
    if set(old_clips) != set(new_clips):
        raise ValueError('Effective clip set changed')
    rig = old[target]['nodes']; rows = {}; failures = []
    for clip in sorted(old_clips):
        o, n = old_clips[clip]['owner'], new_clips[clip]['owner']
        before, after = old[o]['clips'][clip], new[n]['clips'][clip]
        row = {'oldOwner': o, 'newOwner': n, **compare_clip(before, o, after, n),
               'assembledDrift': assembled_drift(rig, target, before, o, after, n)}
        exact = clips_equal(before, o, after, n)
        if library and n == library['name']:
            row['status'] = 'exact' if exact else 'retained-but-different'
        else:
            within = (row['structure'] and row['positionMetres'] <= tolerances['positionMetres']
                      and row['rotationDegrees'] <= tolerances['rotationDegrees']
                      and row['assembledDrift']['metres'] <= tolerances['assembledDriftMetres'])
            row['status'] = 'inherited-exact' if exact else 'inherited-within-tolerance' if within else 'inherited-outside-tolerance'
        if clip in authorized and row['status'] not in ('exact', 'inherited-exact'):
            row['status'] = 'authorized-fit-clip'
        if row['status'] in ('retained-but-different', 'inherited-outside-tolerance'):
            failures.append(clip)
        rows[clip] = row
    counts = {}
    for row in rows.values():
        counts[row['status']] = counts.get(row['status'], 0) + 1
    worst = max(rows.items(), key=lambda kv: kv[1]['assembledDrift']['metres'] if kv[1]['status'] != 'authorized-fit-clip' else -1)
    return {'schemaVersion': 1, 'kind': 'PhenoMorpher-motion-comparison', 'target': target,
            'oldChain': old_chain, 'newChain': new_chain, 'library': {'name': library['name'], 'sha256': digest(library_blob)} if library else None,
            'repointedRoot': {'sha256': digest(repointed), 'parent': new[target]['parent'], 'onlySupermodelFieldChanged': True},
            'tolerances': tolerances, 'authorized': sorted(authorized), 'counts': counts,
            'worstUnauthorizedDrift': {'clip': worst[0], **worst[1]['assembledDrift']},
            'failures': failures, 'passed': not failures, 'clips': rows, 'assetApprovalCreated': False}
