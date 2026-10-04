"""Read-only actual stock weapon component hierarchy and shield strap geometry."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[2]
sys.path.insert(0,str(R/'tools/phenotypes'))
from retarget import NODE,nodes,transforms
from audit_geometry import arrays
from place_purposebuilt_pelvis import require
S=R/'output/phenotypes/human-male-complete-goal-v1/stock-grip-inputs-v1'
O=P/'equipment-measurement-v1';O.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[]
for model in ['wswls_t_011','wswls_m_011','wswls_b_011','ashsw_011']:
    path=S/'ascii'/(model+'.mdl');text=path.read_text();world=transforms(nodes(text));parts=[]
    for m in NODE.finditer(text.split('endmodelgeom')[0]):
        v=np.asarray(arrays(m[3],'verts'));f=np.asarray(arrays(m[3],'faces'))
        if not len(v):continue
        p=(world[m[2].lower()]@np.c_[v,np.ones(len(v))].T).T[:,:3]
        record={'node':m[2],'vertices':len(v),'triangles':len(f),'hierarchyMatrix':world[m[2].lower()].tolist(),'bounds':[p.min(0).tolist(),p.max(0).tolist()],'extentMm':(np.ptp(p,axis=0)*1000).tolist()}
        if model=='wswls_b_011':
            # Original eight axial handle vertices are distinct from six pommel points.
            shaft=p[6:14];require(len(v)==14 and len(f)==18,'Reviewed stock handle topology changed')
            lower=shaft[np.argsort(shaft[:,1])[:4]];upper=shaft[np.argsort(shaft[:,1])[-4:]]
            a,b=lower.mean(0),upper.mean(0);axis=b-a;axis/=np.linalg.norm(axis)
            record['shaft']={'originalVertexIds':list(range(6,14)),'lowerCenter':a.tolist(),'upperCenter':b.tolist(),'measuredAxis':axis.tolist(),'bounds':[shaft.min(0).tolist(),shaft.max(0).tolist()],'lengthMm':float(np.linalg.norm(b-a)*1000),'endDiametersXZMm':[(np.ptp(e[:,[0,2]],axis=0)*1000).tolist() for e in [lower,upper]],'rootOriginOnHandle':'Actual weapon origin lies between lower/upperhandleends; rootXYZ is not exact diamondsectioncenter.'}
        parts.append(record)
    rows.append({'model':model,'path':str(path),'sha256':sha(path),'parts':parts})
inv=S/'inventory.json';require(inv.exists(),'Actual extractor inventory missing')
result={'schemaVersion':1,'readOnly':True,'stockInputsInventory':str(inv),'stockInputsInventorySha256':sha(inv),'models':rows,'weaponRootAxis':'Stock normal longsword handle is local+Y, measured from actual8shaftvertices after hierarchytransform; never assume localZ from dummy.', 'shieldScope':'Actual shield has a transformed disk and closedBox07strap, not a cylindricalhandle. Retain exact stock itemgeometry/scale; pose and handcoverage require independentinspection.','nativeOrClientAccepted':False}
(O/'measurement.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'output':str(O/'measurement.json'),'handle':rows[2]['parts'][0]['shaft']}))
