"""Minimal generated-cap4mm interior bubble; working diagnostic only, no fit/rig edits."""
import numpy as np
import target_contract as tc

def bubble(p,center,radius,depth=.004):
    p=np.asarray(p,float);center=np.asarray(center,float)
    tc.require(p.ndim==2 and p.shape[1]==3 and center.shape==(2,) and np.isfinite(p).all() and np.isfinite(center).all(),'Finite world cap P/XYcenter required')
    tc.require(np.isfinite(radius) and radius>0 and depth==.004,'Exact positive-radius4mm recipe only')
    delta=p[:,:2]-center;u=np.sum(delta*delta,axis=1)/(radius*radius);q=np.maximum(1-u,0);height=-depth*q**3;grad=np.zeros_like(p);grad[:,:2]=6*depth*q[:,None]**2*delta/(radius*radius);J=np.broadcast_to(np.eye(3),(len(p),3,3)).copy();J[:,2,:]+=grad
    return height,grad,J

def map_cap(p,center,radius):
    p=np.asarray(p,float);h,grad,J=bubble(p,center,radius);q=p.copy();active=h!=0;q[active,2]+=h[active];return q

def stored_cap_positions(P,world,center,radius):
    P=np.asarray(P);h,_,_=bubble(world,center,radius);result=P.copy();changed=h!=0;result[changed,1]=(P[changed,1].astype(float)+h[changed]).astype('<f4');tc.require(np.isfinite(result).all(),'Finite serialization required');return result,changed

def shading_rows(faces,changed):
    faces=np.asarray(faces);return np.unique(faces[np.any(np.asarray(changed)[faces],axis=1)])
