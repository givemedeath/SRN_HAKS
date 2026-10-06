"""Offline linear-blend skinning of NWN skin nodes over stock animation clips.

Bone frames come from the shared rigid sampler (rig_pose_audit) applied to the
model's own complete bind hierarchy, with clips inherited along its supermodel
chain. Results are numerical evidence only; engine playback needs the client.
"""
from pathlib import Path

import numpy as np

import mdl_ascii
from robe_common import read, require
from retarget import nodes as skeleton_nodes
from rig_pose_audit import compile_controllers, inherited_clips, sample

MOTION = [
    {"family": "idle", "clip": "pause1"}, {"family": "walk", "clip": "walk"}, {"family": "run", "clip": "run"},
    {"family": "melee", "clip": "1hslashr"}, {"family": "melee", "clip": "2hslashl"},
    {"family": "kick", "clip": "nwkickr"}, {"family": "cast", "clip": "castout"},
    {"family": "raised-arms", "clip": "castup"}, {"family": "bent-arms", "clip": "drink"},
    {"family": "crouch", "clip": "getlow"}, {"family": "kneel", "clip": "kneel"},
    {"family": "sit", "clip": "sitcross"}, {"family": "knockdown", "clip": "kdfnt"},
    {"family": "knockdown", "clip": "gutokdf"}, {"family": "death", "clip": "deadfnt"},
]


class Rig:
    """One model's bind hierarchy plus clips inherited through its supermodel chain."""

    def __init__(self, model_path, chain, ascii_directory):
        self.path = Path(model_path)
        self.chain = list(chain)
        text = self.path.read_text(encoding="cp1252")
        self.model = mdl_ascii.parse(text)
        self.skeleton = skeleton_nodes(text)
        texts = {name: (Path(ascii_directory) / (name + ".mdl")).read_text(encoding="cp1252") for name in chain[1:]}
        texts[chain[0]] = text
        self.clips = inherited_clips(chain, texts)
        self.bind = mdl_ascii.bind_frames(self.model)
        self._controllers = {}

    def frames(self, clip, time):
        if clip is None:
            return self.bind
        require(clip in self.clips, "Clip unavailable through supermodel chain: " + clip)
        if clip not in self._controllers:
            self._controllers[clip] = compile_controllers(self.clips[clip]["body"])
        return sample(self.skeleton, self.clips[clip]["body"], time, controllers=self._controllers[clip])

    def times(self, clip, count):
        length = self.clips[clip]["length"]
        return [round(length * i / (count - 1), 6) for i in range(count)] if count > 1 else [0.0]


def bind_world(rig, node):
    verts = np.asarray(node.arrays["verts"], dtype=float)
    return (rig.bind[node.key] @ np.c_[verts, np.ones(len(verts))].T).T[:, :3]


def skin(rig, node, frames, weights=None, bones=None):
    """World positions of a skin node's vertices under the given bone frames."""
    if weights is None:
        weights, bones = mdl_ascii.skin_matrix(node)
    rest = np.c_[bind_world(rig, node), np.ones(len(weights))]
    out = np.zeros((len(weights), 3))
    for column, bone in enumerate(bones):
        column_weights = weights[:, column]
        if not np.any(column_weights):
            continue
        require(bone in frames and bone in rig.bind, "Skin bone outside bind hierarchy: " + bone)
        matrix = frames[bone] @ np.linalg.inv(rig.bind[bone])
        out += column_weights[:, None] * (matrix @ rest.T).T[:, :3]
    return out


def rigid(rig, node, frames):
    """World positions of a rigid mesh node under the given frames."""
    verts = np.asarray(node.arrays["verts"], dtype=float)
    return (frames[node.key] @ np.c_[verts, np.ones(len(verts))].T).T[:, :3]


def motion_samples(rig, matrix=MOTION, count=9):
    rows = [{"family": "bind", "clip": None, "time": 0.0}]
    for entry in matrix:
        if entry["clip"] in rig.clips:
            rows += [{"family": entry["family"], "clip": entry["clip"], "time": t}
                     for t in rig.times(entry["clip"], count)]
    return rows


def chain_for(extraction_path, model):
    extraction = read(extraction_path)
    stem = Path(model).stem.lower()
    if stem in extraction["robes"]:
        return extraction["robes"][stem]["chain"]
    if stem == extraction["prefix"]:
        return extraction["bodyChain"]
    raise ValueError("Model chain not recorded in extraction: " + stem)
