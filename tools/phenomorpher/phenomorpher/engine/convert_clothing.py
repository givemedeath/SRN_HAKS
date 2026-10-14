"""Compact, topology-independent clothing field. No body or rig writer."""
import json,hashlib,argparse
from pathlib import Path
import numpy as np
from .clothing_core import profile_value

def move(p,m):
 m=np.asarray(m,float);return np.asarray(p)@m[:3,:3].T+m[:3,3]

def section_profile(p):
 p=np.asarray(p,float);low,high=p[:,2].min(),p[:,2].max();length=float(high-low)
 if not np.isfinite(p).all() or length<1e-6:raise ValueError('Invalid part envelope')
 stations=np.linspace(0,1,9);centers=[];radii=[]
 for t in stations:
  slab=p[np.abs((p[:,2]-low)/length-t)<=.14]
  if len(slab)<6:slab=p[np.argsort(np.abs((p[:,2]-low)/length-t))[:max(6,len(p)//20)]]
  a,b=np.min(slab[:,:2],0),np.max(slab[:,:2],0);centers.append((a+b)/2);radii.append(np.maximum((b-a)/2,.003))
 # Broad profiles only; repeated smoothing suppresses body/garment grooves.
 centers=np.array(centers);radii=np.array(radii)
 for _ in range(2):
  centers[1:-1]=(centers[:-2]+2*centers[1:-1]+centers[2:])/4
  radii[1:-1]=(radii[:-2]+2*radii[1:-1]+radii[2:])/4
 return dict(lowerZ=float(low),length=length,stations=stations.tolist(),centers=centers.tolist(),radii=radii.tolist())

def interp(profile,t,key):
 return np.column_stack([profile_value(profile['stations'],np.array(profile[key])[:,k],np.clip(t,0,1))[0] for k in range(2)])

def structural(profile):
 a,b=profile['sourceEnvelope'],profile['targetEnvelope'];s=b['length']/a['length'];m=np.eye(4)*s;m[3,3]=1
 # Uniform scale first; location relative to the actual attachment is retained explicitly.
 m[:3,3]=[0,0,b['lowerZ']-s*a['lowerZ']]
 return m

def deform(p,profile,garment_class='modular-close',stage='source-local',applications=0):
 if applications!=0:raise ValueError('Repeated morphology is forbidden')
 if garment_class not in ('modular-close','modular-loose','rigid-island'):raise ValueError('Skinned/animated clothing needs a separate bind-aware route')
 if stage not in ('source-local','armory-structural'):raise ValueError('Undeclared input space')
 p=np.asarray(p,float)
 if p.ndim!=2 or p.shape[1]!=3 or not len(p) or not np.isfinite(p).all():raise ValueError('Invalid vertex array')
 m=structural(profile);source=p if stage=='source-local' else move(p,np.linalg.inv(m));a,b=profile['sourceEnvelope'],profile['targetEnvelope'];s=m[0,0]
 if profile.get('identity'):return source.copy(),dict(uniformScale=1.,morphApplications=1,runtimeApplications=0)
 t=(source[:,2]-a['lowerZ'])/a['length'];ca,cb=interp(a,t,'centers'),interp(b,t,'centers');ra,rb=interp(a,t,'radii'),interp(b,t,'radii');q=source[:,:2]-ca
 mapped=np.empty_like(source);mapped[:,2]=b['lowerZ']+t*b['length']
 if garment_class=='rigid-island':
  # One similarity for the complete plate, seated using its centroid. No fat deformation of a rigid island.
  center=source.mean(0,keepdims=True);dest,_=deform(center,profile,'modular-close');mapped=source*s+(dest[0]-center[0]*s)
  return mapped,dict(uniformScale=float(s),rigidIsland=True,morphApplications=1,runtimeApplications=0)
 # Radial ease measured along the same anatomical ray. Exterior ease is scaled by
 # segment length only, rather than by the target's added fat. Inside points use
 # a positive affine radial map, so centers and solid cut caps remain well defined.
 r=np.linalg.norm(q,axis=1);u=q/np.maximum(r[:,None],1e-15)
 radius_a=1/np.sqrt(np.maximum(np.sum((u/ra)**2,axis=1),1e-30));radius_b=1/np.sqrt(np.maximum(np.sum((u/rb)**2,axis=1),1e-30))
 inside=r<=radius_a;rho=r/np.maximum(radius_a,1e-15)
 out_radius=np.where(inside,rho*radius_b,radius_b+s*(r-radius_a))
 mapped[:,:2]=cb+u*out_radius[:,None]
 zero=r<1e-14;mapped[zero,:2]=cb[zero]
 return mapped,dict(uniformScale=float(s),radialEasePolicy='source exterior distance times structural segment scale; body replacement respected',morphApplications=1,runtimeApplications=0)

def jacobian(p,profile,kind):
 p=np.asarray(p,float);eps=1e-6;cols=[]
 if kind=='rigid-island':return np.repeat((np.eye(3)*structural(profile)[0,0])[None],len(p),axis=0)
 for k in range(3):
  h=np.zeros(3);h[k]=eps;cols.append((deform(p+h,profile,kind)[0]-deform(p-h,profile,kind)[0])/(2*eps))
 return np.stack(cols,axis=2)

def normals(p,f):
 n=np.zeros_like(p);tri=p[f];c=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
 for i in range(3):np.add.at(n,f[:,i],c)
 length=np.linalg.norm(n,axis=1);n/=np.maximum(length[:,None],1e-30);n[length<1e-20]=[0,0,1];return n

def main():
 q=argparse.ArgumentParser();q.add_argument('--profile',type=Path,required=True);q.add_argument('--input',type=Path,required=True);q.add_argument('--output',type=Path,required=True);q.add_argument('--class',dest='kind',choices=['modular-close','modular-loose','rigid-island'],required=True);a=q.parse_args()
 if a.output.exists():raise ValueError('Output must be fresh')
 spec=json.loads(a.profile.read_text());z=np.load(a.input,allow_pickle=False)
 if 'converted' in z:raise ValueError('Already converted input')
 if 'weights' in z:raise ValueError('Skinned input requires separate route')
 p=z['attachmentLocal'];f=z['faces'];v,proof=deform(p,spec,a.kind);j=jacobian(p,spec,a.kind)
 if np.min(np.linalg.det(j))<=0:raise ValueError('Local fold detected')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 np.savez_compressed(a.output,attachmentLocal=v,bindAssembled=move(v,spec['targetFrame']),faces=f,uv=z['uv'],uvFaces=z['uvFaces'],normals=normals(v,f),converted=np.array([1]))
 print(json.dumps(proof))
if __name__=='__main__':main()
