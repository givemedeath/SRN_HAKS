"""Read explicitly selected installed KEY/BIF resources with bounded offsets.

No override/user directory or worktree executable is consulted. Different bytes
for a requested resource in multiple KEYs are an ambiguity, not a guessed stack.
"""
from pathlib import Path
import struct

from .measurement_common import require, safe_relative, sha, verified, write


def locate(root, keys, names):
    root = Path(root).resolve()
    requested = {Path(name).stem.lower() for name in names}
    output = {name: [] for name in requested}
    for key in keys:
        data = Path(key).read_bytes()
        require(len(data) >= 64 and data[:8] == b'KEY V1  ', 'Invalid installed KEY')
        count, resource_count, files_offset, resources_offset = struct.unpack_from('<IIII', data, 8)
        require(files_offset + count * 12 <= len(data) and resources_offset + resource_count * 22 <= len(data),
                'KEY table outside file')
        files = []
        for index in range(count):
            size, name_offset, name_length, drives = struct.unpack_from('<IIHH', data, files_offset + index * 12)
            require(name_offset + name_length <= len(data), 'KEY filename outside file')
            name = data[name_offset:name_offset + name_length].split(b'\0')[0].decode('ascii').replace('\\', '/')
            files.append(safe_relative(root, name))
        for index in range(resource_count):
            raw_name, kind, identity = struct.unpack_from('<16sHI', data, resources_offset + index * 22)
            name = raw_name.split(b'\0')[0].decode('ascii').lower()
            if kind == 2002 and name in requested:
                bif_index = identity >> 20
                require(bif_index < len(files), 'KEY BIF index outside file list')
                output[name].append({'key': str(Path(key).resolve()), 'bif': str(files[bif_index]),
                                     'index': identity & 0xfffff})
    require(all(output.values()), 'Installed resources unavailable: ' + str([n for n, rows in output.items() if not rows]))
    return output


def resource(row):
    with Path(row['bif']).open('rb') as stream:
        header = stream.read(20)
        require(len(header) == 20 and header[:8] == b'BIFFV1  ', 'Invalid installed BIF')
        count, fixed, offset = struct.unpack_from('<III', header, 8)
        require(row['index'] < count, 'BIF index outside variable resource table')
        stream.seek(offset + row['index'] * 16)
        entry = stream.read(16)
        require(len(entry) == 16, 'Truncated BIF resource entry')
        identity, start, size, kind = struct.unpack('<IIII', entry)
        require(kind == 2002 and (identity & 0xfffff) == row['index'], 'BIF resource identity/type mismatch')
        require(size > 0 and start + size <= Path(row['bif']).stat().st_size, 'BIF data outside file')
        stream.seek(start)
        data = stream.read(size)
        require(len(data) == size, 'Truncated BIF resource')
        return data


def extract(plan, output):
    output = Path(output)
    require(not output.exists(), 'Fresh installed-stock output required')
    for p in plan['inputs']:
        verified(p['path'], p['sha256'])
    output.mkdir(parents=True)
    rows = []
    for name, candidates in plan['resources'].items():
        values = [resource(row) for row in candidates]
        require(all(value == values[0] for value in values), 'Ambiguous installed KEY precedence: ' + name)
        path = output / (name + '.mdl')
        path.write_bytes(values[0])
        rows.append({'path': str(path.resolve()), 'sha256': sha(path), 'installedSources': candidates})
    write(output / 'extraction.json', {'kind': 'measurement-installed-stock', 'resources': rows,
                                       'inputs': plan['inputs'], 'overridesConsulted': False})
    return rows
