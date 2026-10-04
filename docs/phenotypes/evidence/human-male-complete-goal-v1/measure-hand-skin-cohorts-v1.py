"""Measure actual staged hand/selected forearm palette shades near the wrist."""
import json,sys
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(R/'tools/phenotypes'))
from audit_body_material_inputs import ascii_skin_samples,plt_image,sampled
from stage_stock_part import sha,save,require
G=Path(__file__).resolve().parent
out=G/'hand-skin-cohorts-v1';require(not out.exists(),'Fresh cohort receipt required')
palette=G/'stock-equipment-items-v1/raw/pal_skin01.tga'
pins={str(Path(__file__).resolve()):sha(__file__),str(palette):sha(palette)}
rows={}
for side,hand,fore in [('left','handl','forel'),('right','handr','forer')]:
    stage=G/('hand-'+side+'-raw-stage-v1')/'human_male_fit/converted'
    current=G/'native-twelve-v1/human_male_fit/converted'
    for part,base,plane,sign in [(hand,stage,0.,-1.),(fore,current,-.291763,1.)]:
        model='pmh0_'+part+'001';ascii_path=base/'ascii'/(model+'.mdl');plt_path=base/'resources'/(model+'.plt')
        pins.update({str(x):sha(x) for x in [ascii_path,plt_path]})
        p,uv=ascii_skin_samples(ascii_path.read_text(),model)
        area=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)/2
        bary=np.array([[1/3]*3,[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
        q=np.einsum('sc,tcd->tsd',bary,p);u=np.einsum('sc,tcd->tsd',bary,uv)
        shades=sampled(plt_image(plt_path.read_bytes())[:,:,0],u.reshape(-1,2)).reshape(-1,4)
        dist=(q[:,:,2]-plane)*sign;weights=np.repeat(area[:,None]/4,4,axis=1)
        bands=[]
        for lower,upper in [(0.,.01),(.01,.02),(0.,.02)]:
            mask=(dist>=lower)&(dist<upper);require(mask.any(),'Empty wrist shade cohort')
            mean=float(np.average(shades[mask],weights=weights[mask]))
            bands.append({'distanceMetres':[lower,upper],'samples':int(mask.sum()),'areaWeight':float(weights[mask].sum()),'meanShade':mean})
        rows[part]={'planeZMetres':plane,'inwardZSign':sign,'bands':bands}
handmean=np.mean([rows[h]['bands'][2]['meanShade'] for h in ['handl','handr']])
foremean=np.mean([rows[f]['bands'][2]['meanShade'] for f in ['forel','forer']])
offset=int(round(foremean-handmean));out.mkdir()
save(out/'measurement.json',{'schemaVersion':1,'kind':'actual-wrist-palette-shade-cohorts','frozenInputs':pins,'parts':rows,'recommendedHandShadeOffset':offset,'targetForearmMeanShade':float(foremean),'handMeanShade':float(handmean),'normalStrength':1,'geometryOrExistingMaterialsChanged':False,'limits':'Area-weighted actual UV samples in the20mm planes include hidden overlap surfaces. First integer calibration, not client appearance acceptance.'})
print(json.dumps({'offset':offset,'hand':handmean,'fore':foremean,'parts':rows}))
