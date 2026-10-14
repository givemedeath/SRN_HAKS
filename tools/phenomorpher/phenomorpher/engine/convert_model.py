"""Frozen-body static modular clothing conversion. Never writes body inputs.

Input is an ASCII model and a sidecar naming its exact Human Fit basis. All
static ancestors are evaluated once; output keeps nodes, faces, UVs/materials.
Weighted, inherited, animated and already converted models are rejected.
"""
import argparse, hashlib, json, re
from pathlib import Path
import numpy as np
from .convert_clothing import deform, jacobian, move
from .clothing_core import hierarchy_frame

NODE = re.compile(r'^\s*node\s+(\S+)\s+(\S+)\s*\n(.*?)^\s*endnode', re.M|re.S)
MARKER = '# PhenoMorpher clothing morphology applied once'

def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def bound(root, entry):
    p = (root / entry['path']).resolve()
    if not p.is_relative_to(root.resolve()) or sha(p) != entry['sha256']:
        raise ValueError('Escaped or stale input binding: '+entry['path'])
    return p

def array(body, name):
    m = re.search(r'(?mi)^\s*'+name+r'\s+(\d+)\s*\n', body)
    if not m: return np.empty((0, 0))
    rows = body[m.end():].splitlines()[:int(m[1])]
    result = np.array([[float(x) for x in row.split()] for row in rows])
    if len(result) != int(m[1]) or not np.isfinite(result).all(): raise ValueError('Invalid '+name)
    return result

def replace_array(body, name, values):
    m = re.search(r'(?mi)^\s*'+name+r'\s+(\d+)\s*\n', body)
    if not m: raise ValueError('Missing '+name)
    end = m.end()+sum(len(x) for x in body[m.end():].splitlines(keepends=True)[:int(m[1])])
    s = '  '+name+' '+str(len(values))+'\n'+''.join('    '+' '.join(format(float(v), '.12g') for v in row)+'\n' for row in values)
    return body[:m.start()]+s+body[end:]

def field(body, name, default):
    m = re.search(r'(?mi)^\s*'+name+r'\s+([^\n]+)', body)
    return [float(x) for x in m[1].split()] if m else default

def matrix(body):
    xyz = field(body, 'position', [0,0,0]); aa = field(body, 'orientation', [0,0,1,0]); scale = field(body,'scale',[1])[0]
    axis=np.array(aa[:3],float); length=np.linalg.norm(axis); r=np.eye(3)
    if length>1e-14:
        x,y,z=axis/length; k=np.array([[0,-z,y],[z,0,-x],[-y,x,0]]); r+=np.sin(aa[3])*k+(1-np.cos(aa[3]))*(k@k)
    elif abs(aa[3])>1e-12: raise ValueError('Nonzero rotation without axis')
    m=np.eye(4);m[:3,:3]=r*scale;m[:3,3]=xyz;return m

def parse(text):
    if MARKER in text: raise ValueError('Repeated conversion')
    if re.search(r'(?mi)^\s*(newanim|weights|bonemap|boneweights)\b',text): raise ValueError('Animated or weighted model requires bind-aware route')
    sm=re.search(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',text)
    if not sm or sm[1].lower()!='null': raise ValueError('Inherited model unsupported')
    blocks=list(NODE.finditer(text.split('endmodelgeom',1)[0])); nodes=[]
    for b in blocks:
        parent=re.search(r'(?mi)^\s*parent\s+(\S+)',b[3])
        nodes.append(dict(name=b[2],type=b[1].lower(),parent=parent[1] if parent else 'null',matrix=matrix(b[3]).tolist()))
    if not nodes: raise ValueError('No static hierarchy')
    frames={b[2]:hierarchy_frame(nodes,b[2]) for b in blocks}
    return blocks,frames

def convert_text(text, profile, kind):
    blocks,frames=parse(text); meshes=[b for b in blocks if len(array(b[3],'verts'))]
    if not meshes: raise ValueError('No geometry')
    p=[array(b[3],'verts') for b in meshes]; lengths=[len(x) for x in p]
    local=np.concatenate([move(v,frames[b[2]]) for b,v in zip(meshes,p)])
    out,proof=deform(local,profile,kind); j=jacobian(local,profile,kind)
    if np.linalg.det(j).min()<=0: raise ValueError('Folded field')
    if kind=='rigid-island':
        # Rigid islands use one common similarity across every mesh in this file.
        s=proof['uniformScale'];j=np.repeat((np.eye(3)*s)[None],len(local),axis=0)
    replacements=[];start=0;maximum=0.
    for b,v,n in zip(meshes,p,lengths):
        m=frames[b[2]]; q=out[start:start+n]; jj=j[start:start+n]; body=replace_array(b[3],'verts',move(q,np.linalg.inv(m)))
        faces=array(b[3],'faces')
        if not len(faces) or not np.array_equal(faces[:, :3], faces[:, :3].astype(int)): raise ValueError('Invalid faces')
        f=faces[:,:3].astype(int)
        if f.min()<0 or f.max()>=n: raise ValueError('Invalid triangle index')
        old=local[start:start+n]; a=np.cross(old[f[:,1]]-old[f[:,0]],old[f[:,2]]-old[f[:,0]])
        new=np.cross(q[f[:,1]]-q[f[:,0]],q[f[:,2]]-q[f[:,0]])
        fj=jacobian(old[f].mean(1),profile,kind)
        predicted=np.einsum('nji,nj->ni',np.linalg.inv(fj),a)
        if np.any(np.sum(new*predicted,axis=1)<=0): raise ValueError('Inverted or degenerate triangle')
        composite=np.einsum('ij,njk,kl->nil',np.linalg.inv(m[:3,:3]),jj,m[:3,:3])
        normals=array(b[3],'normals'); tangent=array(b[3],'tangents')
        if len(normals):
            if normals.shape!=(n,3): raise ValueError('Normals require explicit vertex association')
            nn=np.einsum('nji,nj->ni',np.linalg.inv(composite),normals); length=np.linalg.norm(nn,axis=1)
            if not np.isfinite(nn).all() or np.any(length<1e-12):raise ValueError('Invalid authored normal')
            nn/=length[:,None];body=replace_array(body,'normals',nn)
        if len(tangent):
            if tangent.shape!=(n,4) or not len(normals):raise ValueError('Tangent association unavailable')
            tt=np.einsum('nij,nj->ni',composite,tangent[:,:3]);tt-=np.sum(tt*nn,axis=1)[:,None]*nn;length=np.linalg.norm(tt,axis=1)
            if not np.isfinite(tt).all() or np.any(length<1e-12):raise ValueError('Invalid authored tangent')
            tt/=length[:,None];body=replace_array(body,'tangents',np.c_[tt,tangent[:,3]])
        # Untouched text carries the faces, all UV sets, material bindings and transforms.
        replacements.append((b.start(),b.end(),f'node {b[1]} {b[2]}\n{body}endnode'))
        maximum=max(maximum,float(np.max(abs(q-old))));start+=n
    for a,b,s in reversed(replacements):text=text[:a]+s+text[b:]
    return MARKER+'\n'+text,{**proof,'meshes':len(meshes),'vertices':len(local),'maximumDisplacementMetres':maximum,'completeHierarchyRetained':True,'topologyUVMaterialsRetained':True}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--release',type=Path,required=True);ap.add_argument('--profile',type=Path,required=True);ap.add_argument('--source-binding',type=Path,required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--class',dest='kind',choices=['modular-close','modular-loose','rigid-island'],required=True);a=ap.parse_args()
    if a.output.exists() or a.output.with_suffix('.receipt.json').exists():raise ValueError('Fresh output required')
    p=json.loads(a.profile.read_text());basis=json.loads(a.source_binding.read_text())
    for key in ('sourceBody','targetBody'):
        body=json.loads(bound(a.release,p[key]).read_text())
        for pin in body['files'].values():bound(a.release,pin)
    if basis.get('body')!=p['sourceBody'] or basis.get('part')!=p['part'] or basis.get('modelSha256')!=sha(a.input) or basis.get('morphApplications')!=0 or basis.get('space')!='model-root-is-source-attachment-local':raise ValueError('Source model/body/part/coordinate binding mismatch')
    text,receipt=convert_text(a.input.read_text(encoding='cp1252'),p,a.kind)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,encoding='cp1252')
    a.output.with_suffix('.receipt.json').write_text(json.dumps({**receipt,'sourceModelSha256':sha(a.input),'profileSha256':sha(a.profile),'outputSha256':sha(a.output),'bodyWritten':False,'runtimeScaleApplications':0,'clientValidated':False},indent=2)+'\n')
if __name__=='__main__':main()
