"""Freeze authoritative Human male master and record female master authority.

This copies verified native resources from srn_body, proves ASCII decompile parity,
and records explicit authority without inferring master status from filenames.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

import numpy as np

# Ensure tools and phenotypes are on path
REPO = Path(__file__).resolve().parents[2]
if str(REPO / 'tools') not in sys.path:
    sys.path.insert(0, str(REPO / 'tools'))
if str(REPO / 'tools/phenotypes') not in sys.path:
    sys.path.insert(0, str(REPO / 'tools/phenotypes'))

from shared_toolchain import sha, load as load_toolchain
from shared_tools import read_json, write_json, resolve_tool


def digest(path: Path | str) -> str:
    return sha(path)


def decode_node(data: bytes, node_name_bytes: bytes) -> dict:
    """Decode a single trimesh node from native binary NWN MDL data."""
    raw_offset, raw_size = struct.unpack_from('<II', data, 4)
    raw_start = 12 + raw_offset
    idx = data.find(node_name_bytes)
    if idx < 32:
        raise ValueError(f"Node {node_name_bytes!r} not found in model section")
    node = idx - 32
    flag = struct.unpack_from('<I', data, node + 0x6c)[0]
    face_offset, count, capacity = struct.unpack_from('<III', data, node + 0x78)
    vertices, texture_count = struct.unpack_from('<HH', data, node + 0x230)
    if not (vertices and count and count == capacity and texture_count == 1):
        raise ValueError(f"Node {node_name_bytes!r} is not a valid packed one-UV trimesh")

    offsets = {
        key: struct.unpack_from('<I', data, node + field)[0]
        for key, field in [
            ('position', 0x22c),
            ('uv', 0x234),
            ('normal', 0x244),
            ('tangent', 0x258),
            ('sign', 0x260),
        ]
    }

    def floats(key: str, width: int) -> np.ndarray:
        offset = offsets[key]
        if offset == 0xFFFFFFFF or offset + vertices * width * 4 > raw_size:
            raise ValueError(f"Missing or out-of-bounds native {key} array")
        result = np.frombuffer(data, '<f4', vertices * width, raw_start + offset).reshape(-1, width)
        if not np.isfinite(result).all():
            raise ValueError(f"Nonfinite native {key} values")
        return result

    faces = np.ndarray((count, 3), dtype='<u2', buffer=data, offset=12 + face_offset + 26, strides=(32, 2))
    if faces.max() >= vertices:
        raise ValueError(f"Face index out of bounds in node {node_name_bytes!r}")

    return {
        'name': node_name_bytes.decode('ascii').rstrip('\0'),
        'vertices': vertices,
        'facesCount': count,
        'position': floats('position', 3),
        'uv': floats('uv', 2),
        'normal': floats('normal', 3),
        'tangent': floats('tangent', 3),
        'sign': floats('sign', 1),
        'faces': faces,
    }


def emit_ascii_model(model: str, nodes_data: list[dict], bitmap_names: list[str]) -> str:
    """Emit clean standard NWN ASCII MDL text from decoded nodes."""
    lines = [
        f'newmodel {model}',
        f'setsupermodel {model} NULL',
        'classification CHARACTER',
        'setanimationscale 1',
        f'beginmodelgeom {model}',
        f'node dummy {model}',
        '  parent NULL',
        'endnode',
    ]

    for node_info, bitmap in zip(nodes_data, bitmap_names):
        name = node_info['name']
        verts = node_info['position']
        normals = node_info['normal']
        uvs = node_info['uv']
        faces = node_info['faces']

        lines.extend([
            f'node trimesh {name}',
            f'  parent {model}',
            f'  bitmap {bitmap}',
            f'  verts {len(verts)}',
        ])
        for v in verts:
            lines.append(f'    {v[0]:.9g} {v[1]:.9g} {v[2]:.9g}')

        lines.append(f'  normals {len(normals)}')
        for n in normals:
            lines.append(f'    {n[0]:.9g} {n[1]:.9g} {n[2]:.9g}')

        lines.append(f'  tverts {len(uvs)}')
        for u in uvs:
            lines.append(f'    {u[0]:.9g} {u[1]:.9g} 0')

        lines.append(f'  faces {len(faces)}')
        for f in faces:
            lines.append(f'    {f[0]} {f[1]} {f[2]} 1 {f[0]} {f[1]} {f[2]} 0')

        lines.append('endnode')

    lines.extend([
        f'endmodelgeom {model}',
        f'donemodel {model}',
        '',
    ])
    return '\n'.join(lines)


def parse_ascii_arrays(text: str) -> list[dict]:
    """Parse mesh arrays from generated ASCII MDL text for decompile parity checks."""
    node_matches = list(re.finditer(r'(?m)^\s*node\s+trimesh\s+(\S+)\s*\n(.*?)^\s*endnode', text, re.S))
    results = []
    for m in node_matches:
        name = m.group(1)
        body = m.group(2)

        def read_arr(label: str, width: int) -> np.ndarray:
            match = re.search(r'(?mi)^\s*' + label + r'\s+(\d+)\s*\n', body)
            if not match:
                raise ValueError(f"Array {label} not found in node {name}")
            count = int(match.group(1))
            start = match.end()
            raw_lines = body[start:].splitlines()[:count]
            vals = [[float(x) for x in line.split()[:width]] for line in raw_lines]
            return np.asarray(vals, dtype=np.float32)

        def read_faces() -> np.ndarray:
            match = re.search(r'(?mi)^\s*faces\s+(\d+)\s*\n', body)
            if not match:
                raise ValueError(f"Faces not found in node {name}")
            count = int(match.group(1))
            start = match.end()
            raw_lines = body[start:].splitlines()[:count]
            vals = [[int(x) for x in line.split()[:3]] for line in raw_lines]
            return np.asarray(vals, dtype=np.uint16)

        results.append({
            'name': name,
            'position': read_arr('verts', 3),
            'normal': read_arr('normals', 3),
            'uv': read_arr('tverts', 2),
            'faces': read_faces(),
        })
    return results


def check_decompile_parity(native_nodes: list[dict], parsed_nodes: list[dict]) -> dict:
    """Verify maximum error between native binary decode and parsed ASCII text."""
    if len(native_nodes) != len(parsed_nodes):
        raise ValueError("Node count mismatch in parity check")

    max_pos_err = 0.0
    max_norm_err = 0.0
    max_uv_err = 0.0
    total_verts = 0
    total_faces = 0

    for nat, asc in zip(native_nodes, parsed_nodes):
        if nat['name'] != asc['name']:
            raise ValueError(f"Node name mismatch: {nat['name']} vs {asc['name']}")
        p_err = float(np.abs(nat['position'] - asc['position']).max())
        n_err = float(np.abs(nat['normal'] - asc['normal']).max())
        u_err = float(np.abs(nat['uv'] - asc['uv']).max())
        if not np.array_equal(nat['faces'], asc['faces']):
            raise ValueError(f"Face topology mismatch in node {nat['name']}")

        max_pos_err = max(max_pos_err, p_err)
        max_norm_err = max(max_norm_err, n_err)
        max_uv_err = max(max_uv_err, u_err)
        total_verts += len(nat['position'])
        total_faces += len(nat['faces'])

    # Float32 to ASCII format (.9g) preserves float32 within 1e-6
    if max_pos_err > 1e-6 or max_norm_err > 1e-6 or max_uv_err > 1e-6:
        raise ValueError(
            f"Parity check exceeded tolerance: pos={max_pos_err}, norm={max_norm_err}, uv={max_uv_err}"
        )

    return {
        'totalVertices': total_verts,
        'totalFaces': total_faces,
        'maxPositionError': max_pos_err,
        'maxNormalError': max_norm_err,
        'maxUvError': max_uv_err,
        'passed': True,
    }


def freeze_human_male_master(
    manifest_path: Path,
    output_dir: Path,
    toolchain_path: Path | None = None,
    game_root: Path | None = None,
) -> dict:
    """Freeze the accepted Human male master, emit verified ASCII, and record proof."""
    manifest = read_json(manifest_path)
    if manifest.get('status') != 'user-accepted-current-human-male-baseline':
        raise ValueError(f"Unexpected master status: {manifest.get('status')}")

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    native_out = out / 'native'
    ascii_out = out / 'ascii'
    stock_out = out / 'stock'
    for d in (native_out, ascii_out, stock_out):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Verify all resources in srn_body against manifest and copy to native/
    resource_pins = {}
    for item in manifest['resources']:
        src = REPO / item['path']
        if not src.is_file():
            raise FileNotFoundError(f"Missing master resource: {src}")
        actual_sha = sha(src)
        if actual_sha != item['sha256']:
            raise ValueError(f"Hash drift in master resource {src}: expected {item['sha256']}, got {actual_sha}")
        dst = native_out / src.name
        if not dst.exists() or sha(dst) != actual_sha:
            shutil.copyfile(src, dst)
        dest_sha = sha(dst)
        if dest_sha != actual_sha:
            raise ValueError(f"Destination hash mismatch for {dst}: expected {actual_sha}, got {dest_sha}")
        resource_pins[src.name] = {
            'sha256': dest_sha,
            'bytes': item['bytes'],
            'path': str(dst),
        }

    # 2. Decompile each of the 14 models to ASCII with parity proof
    models = sorted([name for name in resource_pins if name.endswith('.mdl')])
    if len(models) != 14:
        raise ValueError(f"Expected 14 body models, found {len(models)}")

    parity_reports = {}
    for model_name in models:
        model_stem = model_name[:-4]
        data = (native_out / model_name).read_bytes()

        if model_stem == 'pmh0_pelvis001':
            nodes_data = [
                decode_node(data, b'pmh0_pelvis001p\0'),
                decode_node(data, b'pmh0_pelvis001f\0'),
            ]
            bitmaps = ['pmh0_pelvis001', 'pmh0_pelvis001f']
        else:
            node_bytes = (model_stem + 'p\0').encode('ascii')
            nodes_data = [decode_node(data, node_bytes)]
            bitmaps = [model_stem]

        ascii_text = emit_ascii_model(model_stem, nodes_data, bitmaps)
        parsed_nodes = parse_ascii_arrays(ascii_text)
        parity = check_decompile_parity(nodes_data, parsed_nodes)
        parity_reports[model_stem] = parity

        ascii_file = ascii_out / f"{model_stem}.mdl"
        ascii_file.write_text(ascii_text, encoding='cp1252')
        parity['asciiSha256'] = sha(ascii_file)

    # 3. Extract stock references if game_root provided
    stock_pins = {}
    if game_root and Path(game_root).is_dir():
        resman = resolve_tool('resman_cat', REPO)['path']
        ud = REPO / '.tmp/scratch/empty-userdir'
        ud.mkdir(parents=True, exist_ok=True)
        stock_models = [
            'pmh0.mdl', 'a_ba.mdl', 'pmh0_head001.mdl', 'pmh0_neck001.mdl',
            'pmd0.mdl', 'pmd0_head001.mdl', 'pmd0_neck001.mdl',
            'pme0.mdl', 'pme0_head001.mdl', 'pme0_neck001.mdl',
            'pmo0.mdl', 'pmo0_head001.mdl', 'pmo0_neck001.mdl'
        ]
        for sm in stock_models:
            target = stock_out / sm
            res = subprocess.run(
                [str(resman), '--root', str(game_root), '--userdirectory', str(ud), '--no-ovr', sm],
                capture_output=True,
                check=True,
            )
            extracted = res.stdout
            if not target.exists() or target.read_bytes() != extracted:
                target.write_bytes(extracted)
            stock_pins[sm] = {
                'path': str(target),
                'sha256': sha(target),
                'bytes': target.stat().st_size,
            }

    receipt = {
        'schemaVersion': 1,
        'kind': 'derived-master-freeze',
        'target': 'human-male',
        'status': manifest['status'],
        'replaces': manifest['replaces'],
        'stockRig': manifest['stockRig'],
        'assemblyHeightMetres': manifest['assemblyHeightMetres'],
        'sourceManifest': str(manifest_path.resolve()),
        'sourceManifestSha256': sha(manifest_path),
        'sourceImplementationCommit': manifest['sourceImplementationCommit'],
        'resourceCount': len(resource_pins),
        'resources': resource_pins,
        'decompileParity': parity_reports,
        'stockReferences': stock_pins,
    }

    receipt_file = out / 'master-freeze.json'
    write_json(receipt_file, receipt, fresh=True)
    return receipt


def record_female_master_status(output_dir: Path, female_ledger: Path | None = None) -> dict:
    """Record Human female master status as blocked-on-source with provenance."""
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    declared_ledger = Path(female_ledger).resolve() if female_ledger else None
    female_ledger_sha = sha(declared_ledger) if (declared_ledger and declared_ledger.is_file()) else None

    receipt = {
        'schemaVersion': 1,
        'kind': 'derived-master-freeze',
        'target': 'human-female',
        'status': 'blocked-on-source',
        'reason': (
            'Human female purpose-built session is paused at restart checkpoint v24; '
            'final body selection and global female animation overlay remain unapproved.'
        ),
        'femaleLedgerProvenance': {
            'path': str(declared_ledger) if (declared_ledger and declared_ledger.is_file()) else None,
            'sha256': female_ledger_sha,
        },
        'allowedAction': 'Wait for human female master approval before deriving female race variants.',
    }

    receipt_file = out / 'master-freeze.json'
    write_json(receipt_file, receipt, fresh=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=REPO / 'docs/phenotypes/human-male-assets.json')
    parser.add_argument('--output-dir', type=Path, default=REPO / 'output/phenotypes/derived-v1/masters')
    parser.add_argument('--game-root', type=Path, default=Path(r'C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition'))
    parser.add_argument('--female-ledger', type=Path, default=None, help='Declared Human female selection ledger binding')
    parser.add_argument('--toolchain', type=Path)
    args = parser.parse_args()

    print("Freezing Human male master...")
    male_receipt = freeze_human_male_master(
        args.manifest,
        args.output_dir / 'human-male-v1',
        toolchain_path=args.toolchain,
        game_root=args.game_root if args.game_root.is_dir() else None,
    )
    print(f"Human male master frozen: {male_receipt['resourceCount']} resources, 14 models verified with exact parity.")

    print("Recording Human female master status...")
    female_receipt = record_female_master_status(
        args.output_dir / 'human-female-v1',
        female_ledger=args.female_ledger,
    )
    print(f"Human female status: {female_receipt['status']}.")


if __name__ == '__main__':
    main()
