"""Immutable post-bake native-corner revisions with explicit affine lineage."""
from pathlib import Path
import numpy as np
from tools.headkit.common import pin,verify,require,write
from .grip import affine_corners
from .geometry import topology


def transform_part(source,matrix,output):
    source_pin=pin(source);verify([source_pin]);m=np.asarray(matrix,float)
    with np.load(source,allow_pickle=False) as data:
        require(set(data.files)=={'positions','normals','uv','shadowVertices','shadowFaces'},'Expected native corner archive')
        old={key:data[key].copy() for key in data.files}
    positions,normals,uv=affine_corners(old['positions'],old['normals'],old['uv'],m)
    shadow=old['shadowVertices']@m[:3,:3].T+m[:3,3]
    require(topology(shadow,old['shadowFaces'])['closedWound'],'Transformed shadow must remain closed and outward')
    visible=positions.reshape(-1,3);faces=np.arange(len(visible)).reshape(-1,3)
    require(topology(visible,faces)['closedWound'],'Transformed visible mesh must remain closed and outward')
    retained=[]
    for axis in range(3):
        if np.array_equal(m[axis],np.eye(4)[axis]):
            require(np.array_equal(positions[...,axis],old['positions'][...,axis]) and
                    np.array_equal(shadow[:,axis],old['shadowVertices'][:,axis]),'Protected coordinate changed')
            retained.append(axis)
    output=Path(output);output.mkdir()
    target=output/'corners.npz';np.savez(target,positions=positions,normals=normals,uv=uv,
                                      shadowVertices=shadow,shadowFaces=old['shadowFaces'])
    verify([source_pin])
    result={'source':source_pin,'corners':pin(target),'matrix':m.tolist(),'retainedAxes':retained,
            'uvExact':True,'nativeNormals':'analytic inverse transpose','appearanceFieldSampled':False,
            'visibleTriangles':len(positions),'shadowTriangles':len(old['shadowFaces']),
            'clientValidated':False,'productionAccepted':False}
    write(output/'receipt.json',result,fresh=True);return result
