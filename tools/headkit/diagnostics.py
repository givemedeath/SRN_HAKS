"""Small CPU ray-cast sheets. Measurements and evidence never approve appearance."""
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw
from .common import pin, require, write, verify
from .gltf import mesh
from .rays import EmbreeScene

VIEWS={'front':(0,0),'left-three-quarter':(45,0),'right-three-quarter':(-45,0),
       'left-back-three-quarter':(135,0),'right-back-three-quarter':(-135,0),
       'back':(180,0),'jaw-underside':(0,-75),'crown':(0,75),
       'left temple 50 degrees':(50,0),'left temple profile':(90,0),
       'right temple 50 degrees':(-50,0),'right temple profile':(-90,0)}

def views(value,dll,size,names):
    positions=value['positions'].astype(float);faces=value['faces']
    low,high=positions.min(0),positions.max(0);center=(low+high)/2
    span=float(np.linalg.norm(high-low))*1.08
    require(span>0 and 32<=size<=512,'Bounded nonempty diagnostic')
    scene=EmbreeScene(dll,positions.astype(np.float32),faces.astype(np.uint32))
    try:
        for name in names:
            yaw,tilt=map(math.radians,VIEWS[name])
            toward=np.array([math.sin(yaw)*math.cos(tilt),math.sin(tilt),math.cos(yaw)*math.cos(tilt)])
            right=np.array([math.cos(yaw),0,-math.sin(yaw)]);up=np.cross(toward,right)
            ys,xs=np.mgrid[0:size,0:size]
            frame = (high-low).max()*1.08 if 'temple' in name else span
            org=center+toward*span*2+((xs.ravel()+.5)/size-.5)[:,None]*frame*right+(.5-(ys.ravel()+.5)/size)[:,None]*frame*up
            depth,ids,_=scene.query(org,-toward);hit=ids>=0;indices=np.where(hit,ids,0)
            point=org-np.where(hit,depth,0)[:,None]*toward
            a,b,c=(positions[faces[indices,i]] for i in range(3));v0,v1,v2=b-a,c-a,point-a
            d00,d01,d11=(np.einsum('ij,ij->i',x,y) for x,y in ((v0,v0),(v0,v1),(v1,v1)))
            d20=np.einsum('ij,ij->i',v2,v0);d21=np.einsum('ij,ij->i',v2,v1)
            denominator=d00*d11-d01*d01;denominator=np.where(denominator==0,1,denominator)
            u=(d11*d20-d01*d21)/denominator;v=(d00*d21-d01*d20)/denominator
            normals=np.cross(v0,v1);normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
            shade=np.clip(np.abs(normals@toward)*.7+.2,0,1)
            yield name,{'hit':hit,'face':indices,'bary':np.c_[1-u-v,u,v],'shade':shade,'size':size}
    finally:scene.close()

def pixels(view,colour=None,uv=None):
    size=view['size'];out=np.full((size*size,3),35.,dtype=float);hit=view['hit']
    if colour is None:out[hit]=view['shade'][hit,None]*230
    else:
        t=(view['bary'][hit,:,None]*uv[view['face'][hit]]).sum(1)
        # Bilinear sampling after PLT decoding approximates texture filtering, not channel interpolation.
        xy=np.clip(t,0,1)*(np.array(colour.shape[1::-1])-1);lo=np.floor(xy).astype(int);hi=np.minimum(lo+1,np.array(colour.shape[1::-1])-1)
        f=xy-lo;x,y=lo.T;X,Y=hi.T;a,b=f.T
        out[hit]=(colour[y,x]*(1-a)[:,None]*(1-b)[:,None]+colour[y,X]*a[:,None]*(1-b)[:,None]+
                  colour[Y,x]*(1-a)[:,None]*b[:,None]+colour[Y,X]*a[:,None]*b[:,None])
    return Image.fromarray(np.uint8(np.clip(out.reshape(size,size,3),0,255)))

def sheet(tiles,path,size,columns=4):
    rows=math.ceil(len(tiles)/columns);out=Image.new('RGB',(columns*size,rows*(size+36)),(25,25,25));draw=ImageDraw.Draw(out)
    for i,(label,image) in enumerate(tiles):
        x=i%columns*size;y=i//columns*(size+36);out.paste(image,(x,y+36));draw.text((x+3,y+3),label,fill='white')
    out.save(path);return pin(path)

def geometry_sheet(source,dll,path,size=256):
    value=mesh(source)
    tiles = []
    for name, view in views(value,dll,size,VIEWS):
        tiles.append((name,pixels(view)))
    return sheet(tiles,path,size)

def palette_sheet(source,shades_path,layers_path,palettes,rows,dll,output,size=128):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    paths=[source,shades_path,layers_path,*palettes.values(),dll];inputs=[pin(p) for p in paths]
    value=mesh(source)
    with Image.open(shades_path) as im:shades=np.asarray(im).copy()
    with Image.open(layers_path) as im:layers=np.asarray(im).copy()
    require(shades.shape==layers.shape and shades.ndim==2,'Matching PLT shade/layer maps required')
    tables={}
    for key,path in palettes.items():
        with Image.open(path) as im:tables[str(key)]=np.asarray(im.convert('RGB')).copy()
    base={str(k):v for k,v in rows.items()};looks=[('chosen',base)]
    for channel,alternates in {'0':(3,13),'1':(5,117),'8':(0,26),'9':(0,26),'2':(1,5),'3':(1,5)}.items():
        if channel not in tables or not np.any(layers==int(channel)):continue
        for row in alternates:
            if row!=base.get(channel) and row<len(tables[channel]):looks.append((f'ch{channel} row{row}',dict(base,**{channel:row})))
    names=('front','left-three-quarter','right-three-quarter','left-back-three-quarter','right-back-three-quarter')
    projected=list(views(value,dll,size,names));tiles=[]
    for label,look in looks:
        decoded=np.zeros(shades.shape+(3,),np.uint8)
        for channel in np.unique(layers):
            key=str(int(channel));require(key in tables and key in look,'Missing palette for mapped channel '+key)
            row=look[key];require(type(row) is int and 0<=row<len(tables[key]),'Invalid palette row')
            mask=layers==channel;decoded[mask]=tables[key][row,shades[mask]]
        tiles.extend((label+'\n'+name,pixels(view,decoded,value['uv'])) for name,view in projected)
    image=sheet(tiles,output/'sheet.png',size,columns=len(names))
    verify(inputs,fresh=True)
    result={'inputs':inputs,'sheet':image,'looks':[{'label':name,'rows':look} for name,look in looks],
            'pixelSize':size,'views':list(names),'visualReviewRequired':True,'clientEquivalent':False,
            'limitation':'Fixed 128px head framing and unlit decoded PLT; verify lighting and screen size in the client.'}
    write(output/'evidence.json',result,fresh=True);return result
