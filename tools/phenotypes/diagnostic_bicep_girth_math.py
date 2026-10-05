"""Scoped LEFT upper-arm110% transverse math; no fit, rig or shelf-producing window."""
import numpy as np
import target_contract as tc
FACTOR=1.10

def matrix(origin,distal,factor=FACTOR):
    tc.require(type(factor) is float and factor==FACTOR,'Exact requested arm110 girth factor')
    a=np.asarray(origin,float);b=np.asarray(distal,float);tc.require(a.shape==b.shape==(3,) and np.isfinite(a).all() and np.isfinite(b).all(),'Finite frozen shoulder/elbow positions');d=b-a;L=float(np.linalg.norm(d));tc.require(L>1e-8,'Distinct shoulder and elbow');d/=L;J=FACTOR*np.eye(3)+(1-FACTOR)*np.outer(d,d);M=np.eye(4);M[:3,:3]=J;M[:3,3]=a-J@a;return M,d,L

def points(p,M):
    p=np.asarray(p,float);tc.require(p.ndim==2 and p.shape[1]==3 and np.isfinite(p).all(),'Finite active arm points');return p@M[:3,:3].T+M[:3,3]

def shading(n,t,J):
    n=np.asarray(n,float);t=np.asarray(t,float);J=np.asarray(J,float);tc.require(n.ndim==2 and n.shape[1]==3 and t.shape==(len(n),4) and J.shape==(3,3) and np.isfinite(n).all() and np.isfinite(t).all() and np.isfinite(J).all() and np.linalg.det(J)>0,'Finite proper constant arm field');nm=np.linalg.norm(n,axis=1);tm=np.linalg.norm(t[:,:3],axis=1);tc.require((nm>1e-8).all() and (tm>1e-8).all() and (abs(t[:,3])==1).all(),'Valid active authoredN/T/W');nn=np.linalg.solve(J.T,n.T).T;nn*= (nm/np.linalg.norm(nn,axis=1))[:,None];u=nn/nm[:,None];tt=t.copy();v=t[:,:3]@J.T;v-=np.sum(v*u,axis=1)[:,None]*u;tc.require((np.linalg.norm(v,axis=1)>1e-8).all(),'Collapsed active tangent');tt[:,:3]=v*(tm/np.linalg.norm(v,axis=1))[:,None];return nn,tt
