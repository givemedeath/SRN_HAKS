"""Strict single-primitive GLB transport; transformed/rigged layouts fail explicitly."""
import json,struct
import numpy as np
JSON=0x4e4f534a;BIN=0x004e4942
DTYPES={5120:np.dtype("i1"),5121:np.dtype("u1"),5122:np.dtype("<i2"),5123:np.dtype("<u2"),5125:np.dtype("<u4"),5126:np.dtype("<f4")}
WIDTHS={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4}

def load(payload):
 if len(payload)<28 or struct.unpack_from('<III',payload)!=(0x46546c67,2,len(payload)):raise ValueError('Invalid GLB header')
 chunks={};offset=12
 while offset<len(payload):
  if offset+8>len(payload):raise ValueError('Truncated chunk')
  size,kind=struct.unpack_from('<II',payload,offset);offset+=8
  if size%4 or kind not in (JSON,BIN) or kind in chunks or offset+size>len(payload):raise ValueError('Unsupported GLB chunk layout')
  chunks[kind]=payload[offset:offset+size];offset+=size
 if set(chunks)!={JSON,BIN}:raise ValueError('Embedded JSON/BIN required')
 d=json.loads(chunks[JSON]);b=chunks[BIN]
 if d.get('skins') or d.get('animations') or d.get('extensionsRequired') or d.get('extensionsUsed'):raise ValueError('Unsupported skin/animation/extension')
 if len(d.get('buffers',[]))!=1 or d['buffers'][0].get('uri') is not None or not 0<=d['buffers'][0]['byteLength']<=len(b):raise ValueError('Unsupported buffer')
 if len(d.get('meshes',[]))!=1 or len(d['meshes'][0].get('primitives',[]))!=1:raise ValueError('One primitive required')
 p=d['meshes'][0]['primitives'][0]
 if p.get('mode',4)!=4 or p.get('targets') or p.get('extensions') or 'indices' not in p:raise ValueError('Unsupported primitive')
 for node in d.get('nodes',[]):
  if any(k in node for k in ('matrix','rotation','translation','scale')):raise ValueError('Transformed node unsupported')
 return d,b,p

def accessor(d,b,index):
 if type(index)!=int or not 0<=index<len(d['accessors']):raise ValueError('Invalid accessor index')
 a=d['accessors'][index]
 if 'sparse' in a or a.get('normalized') or a.get('extensions') or type(a.get('count'))!=int or a['count']<1 or a.get('componentType') not in DTYPES or a.get('type') not in WIDTHS:raise ValueError('Unsupported accessor')
 vi=a.get('bufferView')
 if type(vi)!=int or not 0<=vi<len(d['bufferViews']):raise ValueError('Invalid bufferView')
 v=d['bufferViews'][vi];dtype=DTYPES[a['componentType']];width=WIDTHS[a['type']];start=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',dtype.itemsize*width)
 if v.get('buffer',0)!=0 or v.get('extensions') or type(v.get('byteOffset',0))!=int or v.get('byteOffset',0)<0 or type(start)!=int or start<0 or start%dtype.itemsize or type(stride)!=int or stride<dtype.itemsize*width or stride%dtype.itemsize or type(v.get('byteLength'))!=int or v['byteLength']<0:raise ValueError('Invalid accessor stride/offset')
 end=start+(a['count']-1)*stride+dtype.itemsize*width
 if a.get('byteOffset',0)<0 or end>v.get('byteOffset',0)+v['byteLength'] or end>d['buffers'][0]['byteLength'] or end>len(b):raise ValueError('Accessor escapes buffer')
 values=np.ndarray((a['count'],width),dtype=dtype,buffer=b,offset=start,strides=(stride,dtype.itemsize)).copy()
 if not np.isfinite(values).all():raise ValueError('Nonfinite attribute')
 return values

def arrays(d,b,p):
 attrs={k:accessor(d,b,i) for k,i in p['attributes'].items()}
 pos=attrs.get('POSITION')
 if pos is None or pos.ndim!=2 or pos.shape[1]!=3 or d['accessors'][p['attributes']['POSITION']]['componentType']!=5126 or any(len(a)!=len(pos) for a in attrs.values()):raise ValueError('Invalid position/attribute layout')
 index=d['accessors'][p['indices']]
 if index['componentType'] not in (5121,5123,5125) or index['type']!='SCALAR':raise ValueError('Unsigned scalar indices required')
 idx=accessor(d,b,p['indices']).reshape(-1)
 if len(idx)%3 or idx.max()>=len(pos):raise ValueError('Invalid triangle indices')
 return pos,idx.reshape(-1,3),attrs

def encode(d,b):
 j=json.dumps(d,separators=(',',':')).encode();j+=b' '*((-len(j))%4);b+=b'\0'*((-len(b))%4)
 return struct.pack('<III',0x46546c67,2,12+8+len(j)+8+len(b))+struct.pack('<II',len(j),JSON)+j+struct.pack('<II',len(b),BIN)+b

def mesh(path):
    from pathlib import Path
    document, binary, primitive = load(Path(path).read_bytes())
    vertices, faces, attributes = arrays(document, binary, primitive)
    return {'positions': vertices, 'faces': faces.astype(np.int64),
            'normals': attributes.get('NORMAL'),
            'uv': attributes.get('TEXCOORD_0', np.zeros((len(vertices), 2), np.float32))[faces]}


def write_mesh(path, vertices, faces, uv=None, normals=None):
    """Write explicit triangle corners, preserving winding and supplied corner normals."""
    from pathlib import Path
    vertices = np.asarray(vertices, np.float32); faces = np.asarray(faces)
    if (vertices.ndim != 2 or vertices.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3
            or not np.issubdtype(faces.dtype, np.integer) or not len(faces)
            or not np.isfinite(vertices).all() or faces.min() < 0 or faces.max() >= len(vertices)):
        raise ValueError('Finite triangle mesh required')
    corners = vertices[faces]
    if normals is None:
        face_normals = np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0])
        accumulated = np.zeros_like(vertices)
        for i in range(3): np.add.at(accumulated, faces[:, i], face_normals)
        length = np.linalg.norm(accumulated, axis=1)
        if np.any(length == 0): raise ValueError('Undefined vertex normals')
        normals = (accumulated / length[:, None])[faces]
    else:
        normals = np.asarray(normals, np.float32)
        if normals.shape == vertices.shape: normals = normals[faces]
        if normals.shape != corners.shape or not np.isfinite(normals).all():
            raise ValueError('Corner-normal layout differs')
    if uv is not None:
        uv = np.asarray(uv, np.float32)
        if uv.shape != (len(faces), 3, 2) or not np.isfinite(uv).all() or np.any((uv < 0) | (uv > 1)):
            raise ValueError('Finite per-corner UVs in [0,1] required')
    blob = bytearray(); views = []; accessors = []
    def add(array, component, kind, target):
        array = np.ascontiguousarray(array); offset = len(blob); blob.extend(array.tobytes())
        views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': array.nbytes, 'target': target})
        accessors.append({'bufferView': len(views)-1, 'componentType': component, 'count': len(array), 'type': kind,
                          'min': array.min(0).reshape(-1).tolist(), 'max': array.max(0).reshape(-1).tolist()})
        return len(accessors)-1
    attributes = {'POSITION': add(corners.reshape(-1, 3).astype('<f4'), 5126, 'VEC3', 34962),
                  'NORMAL': add(normals.reshape(-1, 3).astype('<f4'), 5126, 'VEC3', 34962)}
    if uv is not None: attributes['TEXCOORD_0'] = add(uv.reshape(-1, 2).astype('<f4'), 5126, 'VEC2', 34962)
    indices = add(np.arange(faces.size, dtype='<u4').reshape(-1, 1), 5125, 'SCALAR', 34963)
    doc = {'asset': {'version': '2.0', 'generator': 'SRN headkit'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
           'nodes': [{'mesh': 0}], 'meshes': [{'primitives': [{'attributes': attributes, 'indices': indices, 'mode': 4}]}],
           'buffers': [{'byteLength': len(blob)}], 'bufferViews': views, 'accessors': accessors}
    result = encode(doc, bytes(blob)); check, binary, primitive = load(result); vv, ff, attrs = arrays(check, binary, primitive)
    if not np.array_equal(vv[ff], corners) or not np.array_equal(attrs['NORMAL'][ff], normals):
        raise ValueError('GLB transport changed corners or normals')
    with Path(path).open('xb') as stream: stream.write(result)
