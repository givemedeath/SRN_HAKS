"""Exact skin corner export using a separately qualified native rig and clip."""
from pathlib import Path
import re,struct
import numpy as np
from tools.headkit.common import require
from tools.itemkit.native import ascii_model


def model_text(name,texture,geometry,rig_text,bone_names):
    bones=list(bone_names)
    require(bones and len(bones)==len(set(bones)) and all(re.fullmatch(r'[a-z0-9_]+',b) for b in bones),'Explicit unique skin bones required')
    old=re.search(r'(?m)^newmodel (\w+)\s*$',rig_text).group(1)
    prefix=rig_text[:rig_text.index('node skin ')];suffix=rig_text[rig_text.index('endmodelgeom '):]
    require(set(re.findall(r'(?m)^node dummy (\w+)\s*$',prefix))=={old,*bones},'Qualified bind tree differs from supplied skin bones')
    rigid=ascii_model(name,texture,geometry['positions'],geometry['normals'],geometry['uv'],geometry['shadowVertices'],geometry['shadowFaces'])
    blocks=re.findall(r'(?ms)^node trimesh .+?^endnode$',rigid);require(len(blocks)==2,'Visible and shadow skin nodes required')
    weights=[np.asarray(geometry['weights']).reshape(-1,len(bones)),np.asarray(geometry['shadowWeights'])[geometry['shadowFaces']].reshape(-1,len(bones))]
    result=[]
    for block,w in zip(blocks,weights):
        count=int(re.search(r'(?m)^  verts (\d+)\s*$',block)[1]);require(w.shape==(count,len(bones)) and np.isfinite(w).all() and (w>=0).all() and np.allclose(w.sum(1),1,atol=1e-7),'Invalid exact skin weights')
        rows=['  weights '+str(count)]+['    '+' '.join(b+' '+format(float(v),'.17g') for b,v in zip(bones,row) if v>0) for row in w]
        result.append(block.replace('node trimesh ','node skin ',1).rsplit('endnode',1)[0]+'\n'.join(rows)+'\nendnode')
    # Whole names only: bones and clips may contain the rig's model name.
    rename=lambda text:re.sub(r'\b'+re.escape(old)+r'\b',name,text)
    return rename(prefix)+'\n'.join(result)+'\n'+rename(suffix)


def decode_meshes(raw):
    from tools.phenomorpher.phenomorpher.engine.anim_library import NativeModel
    from tools.phenomorpher.phenomorpher.engine.stock_armor import native_nodes
    # The existing rig reader bounds the child tree and all controllers first.
    NativeModel(raw).decode()
    zero,raw_offset,raw_size=struct.unpack_from('<III',raw)
    require(zero==0 and 12+raw_offset+raw_size==len(raw),'Invalid skin sections')
    result={}
    for node,flags in native_nodes(raw):
        require(flags in (1,97),'Only qualified dummy/skin geometry permitted')
        if flags!=97:continue
        require(node+0x264<=12+raw_offset,'Truncated skin mesh')
        name=raw[node+32:node+64].split(b'\0')[0].decode('ascii');require(name not in result,'Duplicate skin node')
        faces,count,capacity=struct.unpack_from('<III',raw,node+0x78)
        require(count==capacity and count>0 and faces+count*32<=raw_offset,'Invalid skin face array')
        n,uv_channels=struct.unpack_from('<HH',raw,node+0x230);require(n>0 and uv_channels==1,'Single-UV skin mesh required')
        row={}
        for key,field,width in [('positions',0x22c,3),('normals',0x244,3),('uv',0x234,2)]:
            pointer=struct.unpack_from('<I',raw,node+field)[0]
            require(pointer!=0xffffffff and pointer+n*width*4<=raw_size,'Skin attribute escapes raw section')
            values=np.frombuffer(raw,dtype='<f4',count=n*width,offset=12+raw_offset+pointer).reshape(n,width).copy();require(np.isfinite(values).all(),'Nonfinite skin attribute');row[key]=values
        row['faces']=np.ndarray((count,3),dtype='<u2',buffer=raw,offset=12+faces+26,strides=(32,2)).copy();require(row['faces'].max()<n,'Skin index escapes vertices')
        row['textures']=[raw[node+0xe8+64*k:node+0xe8+64*(k+1)].split(b'\0')[0].decode('ascii') for k in range(4)]
        shadow,_,render=struct.unpack_from('<III',raw,node+0xd4);row['flags']={'render':render,'shadow':shadow};result[name]=row
    require(len(result)==2,'Exactly visible and closed-shadow skins required');return result


def audit(binary,name,texture,expected,decompiled,bone_names):
    from tools.phenomorpher.phenomorpher.engine.stock_armor import sanitize_binary,string_fields,leaked_text
    from tools.itemkit.geometry import topology
    raw=Path(binary).read_bytes();clean=sanitize_binary(raw);allowed=np.zeros(len(raw),bool)
    for offset,count in string_fields(raw):allowed[offset:offset+count]=True
    changed=np.frombuffer(raw,np.uint8)!=np.frombuffer(clean,np.uint8)
    require(not changed[~allowed].any() and clean==sanitize_binary(clean) and not leaked_text(clean),'Skin sanitizer changed non-string bytes or retained leaked tails')
    before,after=decode_meshes(raw),decode_meshes(clean);require(set(after)=={name+'v',name+'s'},'Unexpected skin nodes')
    text=Path(decompiled).read_text(encoding='cp1252');bones=list(bone_names)
    for label,visible in [(name+'v',True),(name+'s',False)]:
        row=after[label];require(row['flags']=={'render':int(visible),'shadow':int(not visible)},'Incorrect skin render/shadow flags')
        require(row['textures'][0].lower()==(texture if visible else 'null') and all(t.lower() in ('','null',texture) for t in row['textures']),'Unexpected skin material dependency')
        for key in ('positions','normals','uv','faces'):require(np.array_equal(before[label][key],row[key]),'Sanitizer changed native skin attributes')
        faces=row['faces'];target=expected['positions'] if visible else expected['shadowVertices'][expected['shadowFaces']]
        require(row['positions'][faces].shape==target.shape and np.allclose(row['positions'][faces],target,atol=2e-6,rtol=0),'Native skin position roundtrip mismatch')
        if visible:
            for key in ('normals','uv'):require(np.allclose(row[key][faces],expected[key],atol=2e-6,rtol=0),'Native skin '+key+' roundtrip mismatch')
        else:require(topology(row['positions'],faces)['closedWound'],'Compiled skinned shadow is not closed/outward')
        body=re.search(r'(?ims)^[ \t]*node skin '+re.escape(label)+r'[ \t]*$(.*?)^[ \t]*endnode',text).group(1)
        def section(key):
            match=re.search(r'(?im)^\s*'+key+r'\s+(\d+)\s*$',body);require(match is not None,'Missing decompiled skin '+key)
            return [line.split() for line in body[match.end():].splitlines() if line.strip()][:int(match[1])]
        p=np.array(section('verts'),float);ff=np.array(section('faces'),float)[:,:3].astype(int);ww=np.zeros((len(p),len(bones)))
        for i,values in enumerate(section('weights')):
            require(len(values)%2==0,'Malformed native skin weight row')
            for j in range(0,len(values),2):ww[i,bones.index(values[j].lower())]=float(values[j+1])
        wanted=expected['weights'] if visible else expected['shadowWeights'][expected['shadowFaces']]
        require(np.allclose(p[ff],target,atol=2e-6,rtol=0) and ww[ff].shape==wanted.shape and np.allclose(ww[ff],wanted,atol=2e-6,rtol=0),'Native skin weight roundtrip mismatch')
    return clean,{'nativePositionNormalUVShadowRoundtrip':True,'nativeWeightRoundtrip':True,'attributesPreserved':True,'zeroedTailBytes':int(changed.sum())}
