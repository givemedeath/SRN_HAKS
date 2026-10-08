"""Single-PLT-per-part body material contract for stock-exact Human targets.

User rule (2026-10-08): each body part model keeps its whole texture in ONE PLT named exactly like the model file;
every node of that model (skin, skin overlay shells, garments) samples it, and garments are encoded in the PLT dye
layers like stock NWN underwear. Each part therefore owns exactly <model>.mdl, .mtr, .plt, n.tga and r.tga; the
complete-body closure is derived from the declared parts (14 x 5 = 70). Retargeted targets keep their historical
layout. These checks read resources only; they never compile, edit pixels or accept visuals.
"""
import re
import struct

import numpy as np

import target_contract as contract

LAYOUT = 'single-plt-per-part-v1'
PART_SUFFIXES = ('.mdl', '.mtr', '.plt', 'n.tga', 'r.tga')
LAYER_NAMES = {0: 'skin', 1: 'hair', 2: 'metal1', 3: 'metal2', 4: 'cloth1', 5: 'cloth2',
               6: 'leather1', 7: 'leather2', 8: 'tattoo1', 9: 'tattoo2'}
SKIN_LAYERS = (0,)
GARMENT_LAYERS = (4, 5)  # stock NWN underwear dyes through the cloth layers
PLT_HEADER = b'PLT V1  '


def applies(target):
    """The single-PLT rule binds the stock-exact Human bodies; other targets keep their declared layout."""
    return contract.rig_mode(target) == 'stock-exact'


def part_resources(model):
    contract.require(re.fullmatch(r'[a-z0-9_]{1,15}', model) is not None and len(model+'n') <= 16,
                     'Single-PLT resref exceeds the native 16-character limit')
    return {model+suffix for suffix in PART_SUFFIXES}


def expected_resources(target, parts):
    parts = set(parts)
    contract.require(parts <= contract.BODY_PARTS, 'Undeclared body/material owner')
    names = set()
    for part in parts:
        names |= part_resources(contract.model(target, part))
    return names


def closure_count(target, parts):
    """Derived resource closure for the declared owners (never a hard-coded total)."""
    return len(expected_resources(target, parts))


def is_single_plt_slots(slots):
    return isinstance(slots, dict) and bool(slots) and all(isinstance(row, dict) and 'pltLayers' in row for row in slots.values())


def validate_slots(slots, nodes=None):
    """Node-keyed slots: {node: {'role': 'skin'|'garment', 'pltLayers': [..]}}; every node samples the model PLT."""
    contract.require(is_single_plt_slots(slots), 'Explicit node-keyed single-PLT material slots required')
    typed = {}
    for node, row in slots.items():
        contract.require(isinstance(node, str) and re.fullmatch(r'[A-Za-z0-9_]{1,32}', node) is not None and
                         set(row) == {'role', 'pltLayers'} and row['role'] in ('skin', 'garment'),
                         'Exact single-PLT node slot required')
        layers = row['pltLayers']
        contract.require(isinstance(layers, list) and layers and len(set(layers)) == len(layers) and
                         all(type(value) is int for value in layers), 'Explicit unique PLT layers required')
        allowed = SKIN_LAYERS if row['role'] == 'skin' else GARMENT_LAYERS
        contract.require(set(layers) <= set(allowed),
                         'Skin uses PLT layer 0 only' if row['role'] == 'skin' else 'Garments use only the stock cloth dye layers')
        typed[node] = {'role': row['role'], 'pltLayers': sorted(layers)}
    if nodes is not None:
        contract.require(set(typed) == set(nodes), 'Single-PLT slots differ from the model node inventory')
    return typed


def node_bindings(text, model):
    """Every trimesh node's bitmap and materialname must equal the model name. Returns trimesh node names."""
    nodes = re.findall(r'(?ms)^\s*node\s+(\S+)\s+(\S+)\s*\n(.*?)^\s*endnode\b', text)
    contract.require(nodes, 'ASCII model has no nodes')
    meshes = []
    for kind, name, body in nodes:
        if kind.lower() != 'trimesh':
            contract.require(kind.lower() == 'dummy', 'Unsupported body node kind: '+kind)
            continue
        for field in ('bitmap', 'materialname'):
            values = [value.lower() for value in re.findall(r'(?mi)^\s*'+field+r'\s+(\S+)\s*$', body)]
            contract.require(values == [model], 'Node '+name+' '+field+' must equal the model name '+model)
        meshes.append(name)
    contract.require(meshes and len(set(meshes)) == len(meshes), 'Unique trimesh nodes required')
    return meshes


def mtr_bindings(text, model):
    """Exactly texture1 <model>n and texture3 <model>r with NormalTangents; no texture0 or other slots."""
    clean = re.sub(r'//[^\n]*', '', text)
    textures = {}
    for slot, name in re.findall(r'(?im)^\s*texture(\d)\s+"?([^\s"]+)', clean):
        contract.require(slot not in textures, 'Duplicate MTR texture slot')
        textures[slot] = name.lower()
    contract.require(textures == {'1': model+'n', '3': model+'r'},
                     'MTR must bind exactly texture1 '+model+'n and texture3 '+model+'r')
    contract.require(re.search(r'(?im)^\s*renderhint\s+"?NormalTangents"?\s*$', clean) is not None,
                     'Body MTR requires NormalTangents')
    return textures


def read_plt(data):
    """(intensity, layer) atlases in top-down image orientation."""
    contract.require(data[:8] == PLT_HEADER and len(data) >= 24, 'PLT V1 header required')
    _, _, width, height = struct.unpack('<IIII', data[8:24])
    contract.require(len(data) == 24+width*height*2, 'PLT size differs from its header')
    pixels = np.frombuffer(data[24:], 'u1').reshape(height, width, 2)[::-1]
    return pixels[..., 0].copy(), pixels[..., 1].copy()


def write_plt(intensity, layer, header_word=10):
    intensity = np.asarray(intensity, np.uint8); layer = np.asarray(layer, np.uint8)
    contract.require(intensity.shape == layer.shape and intensity.ndim == 2, 'Matching 2D PLT planes required')
    height, width = intensity.shape
    pixels = np.ascontiguousarray(np.stack([intensity, layer], -1)[::-1])
    return PLT_HEADER+struct.pack('<IIII', header_word, 0, width, height)+pixels.tobytes()


def layer_audit(layer, nodes, slots):
    """Per node: covered texels use only that node's declared layers; no texel is shared between nodes.

    `nodes` maps node -> (uv (n,2) native bottom-up, faces (m,3)). UVs must lie inside [0,1].
    """
    from uv_atlas_raster import coverage
    typed = validate_slots(slots, nodes)
    height, width = layer.shape
    owner = np.full(layer.shape, -1, np.int32); report = {}
    for index, name in enumerate(sorted(nodes)):
        uv, faces = (np.asarray(value) for value in nodes[name])
        contract.require(np.isfinite(uv).all() and uv.min() >= 0 and uv.max() <= 1, 'UV outside [0,1]: '+name)
        covered = coverage(uv[:, :2], faces, width, height)
        shared = int((covered & (owner >= 0)).sum())
        contract.require(shared == 0, 'Atlas texels shared between nodes: '+name)
        owner[covered] = index
        used = sorted(int(value) for value in np.unique(layer[covered]))
        contract.require(set(used) <= set(typed[name]['pltLayers']),
                         'Node '+name+' samples PLT layers '+str(used)+' outside its declared '+typed[name]['role']+' layers')
        report[name] = {'role': typed[name]['role'], 'declaredLayers': typed[name]['pltLayers'],
                        'usedLayers': used, 'coveredTexels': int(covered.sum())}
    return report


def default_slots(nodes):
    """Legacy skin-only parts: every node is skin on layer 0."""
    return {name: {'role': 'skin', 'pltLayers': [0]} for name in nodes}


def check_part(model, ascii_text, mtr_text, plt_bytes, slots=None):
    """Full single-PLT check of one part from its ASCII source, MTR and PLT bytes."""
    from nwn_ascii_trimesh import AsciiModel
    names = node_bindings(ascii_text, model)
    mtr_bindings(mtr_text, model)
    slots = default_slots(names) if slots is None else slots
    _, layer = read_plt(plt_bytes)
    parsed = AsciiModel(ascii_text); nodes = {}
    for name in names:
        node = parsed.node(name); _, _, tverts, faces = parsed.arrays(node)
        contract.require(np.array_equal(faces[:, 4:7], faces[:, 4:7].astype(np.int64)), 'Integer UV face indices required')
        nodes[name] = (tverts[:, :2], faces[:, 4:7])
    return {'model': model, 'layout': LAYOUT, 'nodes': layer_audit(layer, nodes, slots),
            'textureBindings': {'texture1': model+'n', 'texture3': model+'r'}, 'everyNodeSamplesModelPlt': True}
