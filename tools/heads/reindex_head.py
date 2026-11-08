"""Rename a rigid palette head by editing only its bounded native name fields."""
import argparse
from pathlib import Path
import re
import struct
import numpy as np
from headkit.common import pin, require, write
from headkit.native_reader import decode

MODEL = re.compile(r'p[fm][a-z][0-9]_head[0-9]{3}')

def rename_native(data, old, new):
    require(MODEL.fullmatch(old) and MODEL.fullmatch(new) and old[:4] == new[:4],
            'Head renaming requires the same sex/race/phenotype prefix')
    require(old != new, 'Use a different destination slot')
    policy = dict(require_tangents=False, apply_rigid_transforms=True, allow_constant_alpha=True)
    before = decode(data, old, **policy)
    end = 12 + struct.unpack_from('<I', data, 4)[0]
    result = bytearray(data)
    changes = []
    def bounded(at, size):
        require(12 <= at and at+size <= end, 'Name or hierarchy escapes the model section')
        return at
    def text(at, width):
        bounded(at, width)
        raw = data[at:at+width]
        require(b'\0' in raw, 'Unterminated native name')
        return raw.split(b'\0', 1)[0].decode('ascii')
    def replace(at, width, expected=None):
        name = text(at, width)
        if expected is not None:
            require(name == expected, 'Native model/root name differs from source identity')
        if name == old or name.startswith(old+'p'):
            value = new + name[len(old):]
            require(len(value) == len(name), 'Native rename must preserve field length')
            result[at:at+len(name)] = value.encode('ascii')
            changes.append(dict(offset=at, before=name, after=value))
    replace(20, 64, old)
    require(struct.unpack_from('<I', data, bounded(12+0x7c,4))[0] == 0,
            'Animated heads require an animation-aware renamer')
    root, count = struct.unpack_from('<II', data, bounded(12+0x48,8))
    pending, seen = [root], set()
    while pending:
        offset = pending.pop()
        require(offset not in seen and len(seen) < 32, 'Repeated or excessive native nodes')
        seen.add(offset)
        node = bounded(12+offset, 0x70)
        flags = struct.unpack_from('<I',data,node+0x6c)[0]
        require(flags in (1,33), 'Rigid dummy/trimesh nodes required')
        replace(node+32, 32, old if offset == root else None)
        if flags == 33:
            bounded(node, 0x264)
            for slot in range(4):
                at = node+0xe8+slot*64
                require(text(at,64) in ('','NULL','null',old), 'Unexpected external texture dependency')
                replace(at,64)
        children,n,capacity = struct.unpack_from('<III',data,node+0x48)
        require(n == capacity, 'Unpacked child array')
        at = bounded(12+children, n*4)
        pending.extend(struct.unpack_from('<'+'I'*n,data,at))
    require(len(seen) == count, 'Unvisited native nodes')
    clean = bytes(result)
    require(old.encode('ascii') not in clean[:end], 'Unrecognized source-name field remains')
    require(data[end:] == clean[end:], 'Native vertex payload changed')
    after = decode(clean, new, **policy)
    require(len(before) == len(after), 'Native mesh count changed')
    for a,b in zip(before,after):
        require(set(a) == set(b), 'Native attributes changed')
        for key in a:
            if key in ('name','textures'):
                expected = ([v.replace(old,new) for v in a[key]] if key == 'textures'
                            else a[key].replace(old,new))
                require(b[key] == expected, 'Native name remap differs')
            elif isinstance(a[key],np.ndarray):
                require(np.array_equal(a[key],b[key]), 'Native geometry attribute changed: '+key)
            else:
                require(a[key] == b[key], 'Native material/controller changed: '+key)
    return clean, {'renames':changes, 'geometryAndMaterialsUnchanged':True,
                   'rawPayloadIdentical':True, 'triangles':sum(len(x['faces']) for x in after)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--new-model',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=pin(args.source)
    data,report=rename_native(args.source.read_bytes(),args.source.stem,args.new_model)
    require(args.output.stem == args.new_model and args.output.suffix == '.mdl','Output name differs')
    with args.output.open('xb') as target: target.write(data)
    require(pin(args.source) == source,'Source changed while renaming')
    write(args.output.with_suffix('.rename.json'),dict(report,source=source,output=pin(args.output)),fresh=True)

if __name__ == '__main__':
    main()
