"""Verify atlas-only transfer when Meshy rewrites its returned mesh.

The returned mesh is never selected. Only a proper positive uniform recentering
is undone for comparison. Every matched triangle must preserve winding and UVs;
an explicit reviewed allowance can cover omitted microscopic source triangles.
The selected donor's original baked normal map is retained separately.
"""
import argparse
from pathlib import Path
import numpy as np
from head_export import triangles
from head_workflow import pin,read,require,verify_pins,write_fresh


def cap_only_omissions(missing,areas,source,fit_file,closure_file,review_file=None):
    fit=read(fit_file);closure=read(closure_file)
    verify_pins([fit['source'],closure['output'],closure['source']])
    require(fit['source']==pin(source)==closure['output'] and closure['kind']=='srn-head-cap-only-closure'
            and closure['passed'] is True and closure['originalSurfacePreserved'] is True
            and closure['trimApplied'] is False and closure['taperApplied'] is False,
            'Explicit matching cap-only geometry and fit required')
    scale=fit['uniformScale'];linear=np.asarray(fit['localMatrix'])[:3,:3]
    require(scale>0 and np.allclose(linear.T@linear,np.eye(3)*scale**2,atol=1e-9)
            and np.linalg.det(linear)>0,'Proper uniform fitted scale required for area limits')
    caps={i for hole in closure['holes'] for i in hole['faces']}
    original=[i for i in missing if i not in caps]
    original_area=sum(area*scale**2 for i,area in zip(missing,areas) if i not in caps)
    cap_area=sum(area*scale**2 for i,area in zip(missing,areas) if i in caps)
    maximum=8
    if review_file:
        reviewed=read(review_file);verify_pins([reviewed['source'],reviewed['fit'],reviewed['closure'],*reviewed['evidence']])
        require(reviewed['kind']=='srn-head-atlas-omission-review' and reviewed['passed'] is True
                and reviewed['source']==pin(source) and reviewed['fit']==pin(fit_file)
                and reviewed['closure']==pin(closure_file),'Atlas omission review belongs to another source or fit')
        require(reviewed['omittedOriginalFaceIds']==original and 8<len(original)<=64,
                'Reviewed atlas omission IDs differ or exceed the explicit microface bound')
        maximum=len(original)
    require(len(original)<=maximum and original_area<=1e-6 and cap_area<=1e-5,
            'Omitted atlas correspondence exceeds bounded fitted microface/cap areas')
    return {'fit':pin(fit_file),'closure':pin(closure_file),'omittedOriginalFaceIds':original,
            'omittedCapFaceIds':[i for i in missing if i in caps],
            'originalAreaSquareMetres':original_area,'capAreaSquareMetres':cap_area,
            'allSourceFacesRetained':True,'review':pin(review_file) if review_file else None,
            'capAtlasPolicy':'Locally filled from preserved neighboring material; neutral normal',
            'originalAtlasPolicy':'Fill omitted microface material pixels from preserved adjacent faces; retain original normal bake'}


def canonical(p,n,uv):
    result=[]
    for index,row in enumerate(p):
        j=min(range(3),key=lambda j:tuple(np.round(np.roll(row,j,axis=0).ravel(),5)))
        result.append((np.roll(row,j,axis=0),np.roll(n[index],j,axis=0),np.roll(uv[index],j,axis=0)))
    return result


def verify(source,returned,output,allow_microfaces=False,position_tolerance=2e-6,fit_file=None,closure_file=None,review_file=None):
    require(2e-6<=position_tolerance<=.001,'Explicit bounded atlas correspondence tolerance required')
    p,n,uv=triangles(source,np.eye(4));rp,rn,ruv=triangles(returned,np.eye(4))
    low,high=p.min((0,1)),p.max((0,1));rlow,rhigh=rp.min((0,1)),rp.max((0,1))
    scales=(high-low)/(rhigh-rlow);scale=float(scales.mean())
    require(scale>0 and np.allclose(scales,scale,atol=2e-6,rtol=0),'Retexture changed shape or axes')
    translation=(high+low)/2-scale*(rhigh+rlow)/2
    rp=rp*scale+translation
    a,b=canonical(p,n,uv),canonical(rp,rn,ruv);bins={}
    for i,row in enumerate(a):
        key=tuple(np.floor(row[0].mean(0)*1000).astype(int));bins.setdefault(key,[]).append(i)
    used=set();maximum_p=maximum_uv=maximum_n=0
    for row in b:
        key=np.floor(row[0].mean(0)*1000).astype(int);candidates=[]
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for dz in (-1,0,1):candidates+=bins.get(tuple(key+[dx,dy,dz]),[])
        candidates=[i for i in candidates if i not in used]
        require(candidates,'Returned triangle has no selected source counterpart')
        index,offset=min(((i,j) for i in candidates for j in range(3)),
                         key=lambda pair:np.max(np.abs(a[pair[0]][0]-np.roll(row[0],pair[1],axis=0))))
        row=tuple(np.roll(value,offset,axis=0) for value in row)
        dp=float(np.max(np.abs(a[index][0]-row[0])));du=float(np.max(np.abs(a[index][2]-row[2])))
        require(dp<=position_tolerance and du<=1e-6,f'Retexture changed position, winding or selected UVs: P={dp} UV={du}')
        maximum_p=max(maximum_p,dp);maximum_uv=max(maximum_uv,du)
        maximum_n=max(maximum_n,float(np.max(np.abs(a[index][1]-row[1]))));used.add(index)
    missing=sorted(set(range(len(a)))-used)
    areas=[float(np.linalg.norm(np.cross(p[i,1]-p[i,0],p[i,2]-p[i,0]))/2) for i in missing]
    require(bool(fit_file)==bool(closure_file),'Fitted cap-only allowance needs both fit and closure')
    require(not review_file or fit_file,'Source-specific atlas omission review requires fitted cap-only proof')
    allowance=cap_only_omissions(missing,areas,source,fit_file,closure_file,review_file) if fit_file else None
    require(not missing or allowance is not None or (allow_microfaces and len(missing)<=4 and sum(areas)<=1e-6),
            f'Returned mesh omits source faces outside explicit microscopic transfer allowance: ids={missing}, areas={areas}')
    write_fresh(output,{'kind':'srn-head-atlas-transfer-verification','source':pin(source),'returned':pin(returned),
        'selectedGeometryUnchanged':True,'returnedGeometrySelected':False,'atlasTransferVerified':True,
        'properUniformReframe':{'scale':scale,'translation':translation.tolist()},
        'maximumPositionErrorSourceUnits':maximum_p,'maximumUvError':maximum_uv,'maximumReturnedNormalChange':maximum_n,
        'positionCorrespondenceToleranceSourceUnits':position_tolerance,
        'sourceTriangles':len(p),'returnedTriangles':len(rp),'omittedSourceFaceIds':missing,'omittedSourceAreas':areas,
        'fittedCapOnlyAtlasAllowance':allowance,
        'normalPolicy':'Discard returned normals and generated normal map; retain original selected-donor baked normals. Neutralize new underside cap pixels.',
        'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('source','returned','output'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--allow-microfaces',action='store_true')
    parser.add_argument('--source-position-tolerance',type=float,default=2e-6)
    parser.add_argument('--fit',type=Path);parser.add_argument('--cap-only-closure',type=Path)
    parser.add_argument('--atlas-omission-review',type=Path)
    args=parser.parse_args();verify(args.source,args.returned,args.output,args.allow_microfaces,args.source_position_tolerance,args.fit,args.cap_only_closure,args.atlas_omission_review)
