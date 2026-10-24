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
 nodes=d.get('nodes',[]);scenes=d.get('scenes',[]);scene_index=d.get('scene',0)
 if not isinstance(nodes,list) or not nodes or not isinstance(scenes,list) or type(scene_index)!=int or not 0<=scene_index<len(scenes):raise ValueError('Active scene nodes required')
 for node in nodes:
  if not isinstance(node,dict):raise ValueError('Invalid scene node')
  if any(k in node for k in ('matrix','rotation','translation','scale')):raise ValueError('Transformed node unsupported')
 active=scenes[scene_index]
 roots=active.get('nodes') if isinstance(active,dict) else None
 if not isinstance(roots,list):raise ValueError('Active scene roots required')
 visited=set();instances=0
 def visit(index):
  nonlocal instances
  if type(index)!=int or not 0<=index<len(nodes):raise ValueError('Invalid scene node reference')
  if index in visited:raise ValueError('Multiply-instanced or cyclic scene node')
  visited.add(index);node=nodes[index]
  if 'mesh' in node:
   if type(node['mesh'])!=int or node['mesh']!=0:raise ValueError('Unsupported mesh reference')
   instances+=1
  children=node.get('children',[])
  if not isinstance(children,list):raise ValueError('Invalid scene children')
  for child in children:visit(child)
 for root in roots:visit(root)
 if instances!=1:raise ValueError('Exactly one visible mesh instance required')
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
