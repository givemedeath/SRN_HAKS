"""Read-only stock hand/wrist and held-equipment dummy measurement."""
from pathlib import Path
import sys, json, hashlib
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/phenotypes'))
from audit_geometry import arrays
from retarget import nodes, transforms, NODE
OUT=Path(__file__).resolve().parent/'stock-measurement-v1'
OUT.mkdir(exist_ok=False)
STOCK=ROOT/'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rig=STOCK/'pmh0.mdl';skel=nodes(rig.read_text());world=transforms(skel)
def mesh(path):
    text=path.read_text();mts=transforms(nodes(text));points=[];tris=[]
    for n in NODE.finditer(text.split('endmodelgeom')[0]):
        v=np.asarray(arrays(n[3],'verts'))
        if not len(v):continue
        f=np.asarray(arrays(n[3],'faces'),float)
        p=(mts[n[2].lower()]@np.c_[v,np.ones(len(v))].T).T[:,:3]
        points.extend(p);tris.extend(p[f[:,:3].astype(int)])
    return np.asarray(points),np.asarray(tris)
def section(tri,level):
    hits=[]
    for a,b in ((0,1),(1,2),(2,0)):
        p,q=tri[:,a],tri[:,b];pax=p[:,2];qax=q[:,2]
        ok=(abs(qax-pax)>1e-12)&(np.minimum(pax,qax)<=level)&(np.maximum(pax,qax)>=level)
        t=(level-pax[ok])/(qax[ok]-pax[ok]);hits.extend(p[ok]+(q[ok]-p[ok])*t[:,None])
    h=np.asarray(hits)
    return {'level':float(level),'points':h.tolist(),'bounds': [h.min(0).tolist(),h.max(0).tolist()] if len(h) else None}
def render(tri,view,path,marker):
    d=np.array(view,float);d/=np.linalg.norm(d)
    up=np.array([0.,0.,1.]) if abs(d[2])<.9 else np.array([0.,1.,0.])
    right=np.cross(up,d);right/=np.linalg.norm(right);up=np.cross(d,right)
    pts=tri.reshape(-1,3);center=(pts.min(0)+pts.max(0))/2;scale=300/.18
    xy=np.stack(((tri-center)@right,(tri-center)@up),axis=2)*scale;px=xy*[1,-1]+[210,210]
    im=Image.new('RGB',(420,420),(32,32,32));dr=ImageDraw.Draw(im)
    norm=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1e-20)
    for i in np.argsort((tri.mean(1)-center)@d):
        gray=int(190*(.55+.4*max(0,float(norm[i]@np.array([-.3,.4,.866])))))
        dr.polygon([tuple(x) for x in px[i]],fill=(gray,gray,gray),outline=(68,68,68))
    p=np.array([marker,marker+[0,0,.10],marker+[0,.06,0]])
    q=np.c_[(p-center)@right,-(p-center)@up]*scale+[210,210]
    dr.line([tuple(q[0]),tuple(q[1])],fill=(255,60,60),width=2);dr.line([tuple(q[0]),tuple(q[2])],fill=(60,200,255),width=2)
    dr.ellipse((q[0,0]-4,q[0,1]-4,q[0,0]+4,q[0,1]+4),fill=(255,255,0));im.save(path)
report={'schemaVersion':1,'rig':{'path':str(rig),'sha256':sha(rig),'supermodel':'a_ba','unchanged':True},'sides':[],'scope':'Stock positions, triangle sections and child dummy frames; not a client alignment test.'}
for side in ('l','r'):
    part=STOCK/f'pmh0_hand{side}001.mdl';fore=STOCK/f'pmh0_fore{side}001.mdl';p,t=mesh(part);fp,ft=mesh(fore)
    joint=side+'hand_g';forejoint=side+'forearm_g';weapon=side+'hand';ftoh=np.linalg.inv(world[joint])@world[forejoint]
    fp=(ftoh@np.c_[fp,np.ones(len(fp))].T).T[:,:3];ft=(ftoh@np.c_[ft.reshape(-1,3),np.ones(ft.size//3)].T).T[:,:3].reshape(-1,3,3)
    axis=world[joint][:3,3]-world[forejoint][:3,3];axis/=np.linalg.norm(axis);la=np.linalg.solve(world[joint][:3,:3],axis)
    marker=(np.linalg.inv(world[joint])@world[weapon])[:3,3]
    row={'part':part.stem,'inputs':{str(part):sha(part),str(fore):sha(fore)},'handLocalBounds':[p.min(0).tolist(),p.max(0).tolist()],'handDimensionsMm':(np.ptp(p,axis=0)*1000).tolist(),'handVertices':len(p),'handTriangles':len(t),'wristJointWorld':world[joint].tolist(),'forearmJointWorld':world[forejoint].tolist(),'weaponDummy':weapon,'weaponWorld':world[weapon].tolist(),'weaponInHandFrame':(np.linalg.inv(world[joint])@world[weapon]).tolist(),'wristAxisLocal':la.tolist(),'handAxialBounds':[(p@la).min(),(p@la).max()],'forearmAxialBoundsInHandFrame':[(fp@la).min(),(fp@la).max()],'axialIntervalOverlapMm':float(((fp@la).max()-(p@la).min())*1000),'zSectionsHand':[section(t,v) for v in (-.02,0.,.005)],'zSectionsForearmInHandFrame':[section(ft,v) for v in (-.02,0.,.005)],'images':[]}
    for name,d in [('front',(0,1,0)),('rear',(0,-1,0)),('medial',(1,0,0)),('lateral',(-1,0,0)),('wrist',(0,0,1)),('distal',(0,0,-1))]:
        path=OUT/f'{side}-{name}.png';render(t,d,path,marker);row['images'].append({'path':str(path),'sha256':sha(path)})
    report['sides'].append(row)
report['note']='Red local weapon Z, cyan local weapon Y, yellow held-equipment dummy. Stock hand is a 16-triangle closed mitten proxy; five digits need independent anatomy review.'
(OUT/'measurement.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'path':str(OUT/'measurement.json'),'sides':[{'part':r['part'],'dimensionsMm':r['handDimensionsMm'],'weaponInHandFrame':r['weaponInHandFrame'],'overlapMm':r['axialIntervalOverlapMm']} for r in report['sides']]}))
