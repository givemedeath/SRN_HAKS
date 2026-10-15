"""Motion baselines from the published library chain (Phase 9, additive).

The v13/v14a loaders (morph_preview_pose_v13, morph_motion_evidence_v14a) stay pinned to their
historical carrier sources. New consumers resolve a body's motion the way the client does:
root > shared library or posture layer > installed a_fa/a_ba chain, nearest clip owner first.
"""
from pathlib import Path

import numpy as np

from . import anim_library as lib
from .native_motion import sample, sample_times

KIND = 'PhenoMorpher-motion-baseline-v2'


class Baseline:
    """Effective motion of one published root over its full supermodel chain."""
    def __init__(self, models, origins, prefix):
        if prefix not in models:
            raise ValueError('Root is not a published rig: ' + prefix)
        self.models, self.prefix = models, prefix
        self.chain = lib.chain(prefix, models)
        self.owners = {clip: row['owner'] for clip, row in lib.effective(self.chain, models).items()}
        self.origins = {n: origins[n] for n in self.chain}
        self.bind = sample(models[prefix]['nodes'], {}, 0.)

    def clip(self, name):
        owner = self.owners[name]; return owner, self.models[owner]['clips'][name]

    def frames(self, name, time):
        """World frames of the root's nodes at a clip time; the owner's root node maps to the body root."""
        owner, clip = self.clip(name)
        animated = {(self.prefix if n == owner else n): row for n, row in clip['nodes'].items()}
        return sample(self.models[self.prefix]['nodes'], animated, time)

    def times(self, name):
        return sample_times(self.clip(name)[1])

    def summary(self):
        return {'kind': KIND, 'root': self.prefix, 'chain': self.chain, 'origins': self.origins,
                'clips': len(self.owners), 'owners': dict(sorted(self.owners.items())), 'assetApprovalCreated': False}


def load(root, manifest, stock_manifest, prefixes):
    """Baselines for these roots from a contract (path or dict) and an extracted stock manifest."""
    root = Path(root).resolve()
    if not isinstance(manifest, dict):
        import json
        manifest = json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    stock, stock_paths = lib.stock_files(stock_manifest)
    models, origins = lib.release_models(root, manifest, stock, stock_paths)
    return {p: Baseline(models, origins, p) for p in prefixes}


def max_frame_difference(a, b):
    """Largest absolute element difference between two frame dicts over their shared nodes."""
    shared = set(a) & set(b)
    if not shared:
        raise ValueError('No shared nodes')
    return max(float(np.abs(np.asarray(a[n]) - np.asarray(b[n])).max()) for n in shared)
