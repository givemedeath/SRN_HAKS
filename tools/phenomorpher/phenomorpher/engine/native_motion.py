"""Read-only bounded native character sampler, retaining small quaternion rotations."""
import struct
import numpy as np

class Reader:
    def __init__(self, blob):
        self.blob=blob
        if len(blob)<244:raise ValueError('Truncated native model')
        zero,self.size,self.raw=struct.unpack_from('<III',blob)
        if zero or len(blob)!=12+self.size+self.raw:raise ValueError('Invalid native sections')
    def data(self,p,n):
        if min(p,n)<0 or p+n>self.size:raise ValueError('Out of bounds')
        return self.blob[12+p:12+p+n]
    def u32(self,p):return struct.unpack('<I',self.data(p,4))[0]
    def text(self,p,n):
        b=self.data(p,n)
        if b'\0' not in b:raise ValueError('Unterminated native name')
        return b.split(b'\0')[0].decode('ascii').lower()
    def array(self,p,width):
        off,n,cap=struct.unpack('<III',self.data(p,12))
        if n>cap:raise ValueError('Invalid capacity')
        self.data(off,n*width);return off,n
    def tree(self,root):
        out={};seen=set();q=[(root,None)]
        while q:
            off,parent=q.pop()
            if off in seen:raise ValueError('Cyclic/shared child')
            seen.add(off);self.data(off,112);name=self.text(off+32,32);original=name
            if name in out:
                if name!='impact':raise ValueError('Ambiguous anatomical node '+name)
                i=2
                while name in out:name=original+'__duplicate_'+str(i);i+=1
            ko,nk=self.array(off+84,12);fo,nf=self.array(off+96,4);f=np.frombuffer(self.data(fo,nf*4),'<f4');controls={}
            if not np.isfinite(f).all():raise ValueError('Nonfinite controller')
            for i in range(nk):
                kind,rows,to,vo,cols,pad=struct.unpack('<ihhhbb',self.data(ko+i*12,12))
                if kind in controls or rows<1 or cols<1 or min(to,vo)<0 or to+rows>nf or vo+rows*cols>nf:raise ValueError('Invalid native controller')
                times=f[to:to+rows].astype(float);v=f[vo:vo+rows*cols].reshape(rows,cols).astype(float)
                if np.any(np.diff(times)<0):raise ValueError('Unordered keys')
                if kind in (8,20,36) and cols!={8:3,20:4,36:1}[kind]:raise ValueError('Unsupported transform interpolation')
                controls[kind]={'times':times,'values':v}
            out[name]={'parent':parent,'controls':controls}
            children,n=self.array(off+72,4);q.extend((self.u32(children+4*i),name) for i in range(n))
        return out
    def decode(self):
        nodes=self.tree(self.u32(72));clips={};ptr,count=self.array(120,4)
        for i in range(count):
            off=self.u32(ptr+4*i);name=self.text(off+8,64);length,transition=struct.unpack('<ff',self.data(off+112,8))
            if name in clips or not np.isfinite([length,transition]).all() or length<0:raise ValueError('Invalid animation')
            clips[name]={'nodes':self.tree(self.u32(off+72)),'length':length,'transition':transition}
        return {'name':self.text(8,64),'parent':self.text(168,64),'nodes':nodes,'clips':clips}

def quaternion_matrix(q):
    norm=np.linalg.norm(q)
    if not np.isfinite(norm) or norm<1e-8:raise ValueError('Invalid rotation')
    x,y,z,w=q/norm
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

def value(c,time,rotation=False):
    ts=c['times'];v=c['values']
    if time<=ts[0]:return v[0]
    if time>=ts[-1]:return v[-1]
    i=np.searchsorted(ts,time,side='right');a=(time-ts[i-1])/(ts[i]-ts[i-1]);left=v[i-1];right=v[i]
    if not rotation:return left+a*(right-left)
    left=left/np.linalg.norm(left);right=right/np.linalg.norm(right);dot=np.dot(left,right)
    if dot<0:right=-right;dot=-dot
    if dot>.9995:
        q=left+a*(right-left);return q/np.linalg.norm(q)
    angle=np.arccos(np.clip(dot,-1,1));return (np.sin((1-a)*angle)*left+np.sin(a*angle)*right)/np.sin(angle)

def sample(nodes,animated=None,time=0):
    local={};world={};visiting=set()
    for name,node in nodes.items():
        controls={**node['controls'],**(animated or {}).get(name,{}).get('controls',{})};m=np.eye(4)
        if 8 in controls:m[:3,3]=value(controls[8],time)
        if 20 in controls:m[:3,:3]=quaternion_matrix(value(controls[20],time,True))
        if 36 in controls:
            scale=float(value(controls[36],time)[0])
            if scale<=0:raise ValueError('Nonpositive scale')
            m[:3,:3]*=scale
        local[name]=m
    def visit(name):
        if name in world:return world[name]
        if name not in nodes or name in visiting:raise ValueError('Unresolved parent or cycle')
        visiting.add(name);p=nodes[name]['parent'];world[name]=local[name] if p is None else visit(p)@local[name];visiting.remove(name);return world[name]
    for n in nodes:visit(n)
    return world

def sample_times(clip):
    ts={0.,clip['length']}
    for n in clip['nodes'].values():
        for kind,c in n['controls'].items():
            if kind in (8,20,36):ts.update(x for x in c['times'] if 0<=x<=clip['length'])
    ts=sorted(ts);return sorted(set(ts+[(a+b)/2 for a,b in zip(ts,ts[1:])]))
