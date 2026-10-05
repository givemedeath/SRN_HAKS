"""Prove a new neck connector preserves the textured upper donor surface."""
import argparse
from pathlib import Path
import numpy as np
from head_export import triangles
from head_workflow import pin,read,require,verify_pins,write_fresh
from verify_retexture import corner_error


def audit(previous_fit,previous_correction,fit_path,correction_path,output):
    old=read(previous_fit);new=read(fit_path);before=read(previous_correction);after=read(correction_path)
    verify_pins([old['source'],new['source'],before['output'],after['output']])
    require(old['source']==before['output'] and new['source']==after['output'],'Exact revision sources required')
    previous=triangles(old['source']['path'],old['localMatrix']);selected=triangles(new['source']['path'],new['localMatrix'])
    old_ids=sorted(set(range(len(previous[0])))-set(before.get('connectorFaceIds',before['capFaceIds'])))
    new_ids=sorted(set(range(len(selected[0])))-set(after['connectorFaceIds']))
    require(len(old_ids)==len(new_ids),'Upper donor surface face count changed')
    errors=corner_error([p[old_ids] for p in previous],[p[new_ids] for p in selected],2e-6)
    require(float(errors.max())<=2e-6,'Upper positions/normals/UVs changed; fresh texturing correspondence required')
    write_fresh(output,{'kind':'srn-head-texture-inheritance-audit','passed':True,'previousFit':pin(previous_fit),'fit':pin(fit_path),
        'previousCorrection':pin(previous_correction),'correction':pin(correction_path),'source':new['source'],
        'upperSurfaceTriangles':len(new_ids),'maximumCornerAttributeError':float(errors.max()),'originalAtlasReusable':True,
        'newConnectorMaterial':'skin palette; neutral normal; explicit roughness in separately reserved unused UV patch',
        'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('previous-fit','previous-correction','fit','correction','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();audit(a.previous_fit,a.previous_correction,a.fit,a.correction,a.output)
