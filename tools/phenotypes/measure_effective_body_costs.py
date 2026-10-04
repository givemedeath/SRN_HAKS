"""Measure current native payload/mesh costs; label texture memory estimates."""
import argparse
import json
from pathlib import Path
import struct

from PIL import Image
from audit_geometry import arrays
from effective_body_contract import validate_effective_body
from retarget import NODE
from stage_stock_part import require, sha, save


def mip_pixels(width,height):
    result=width*height
    while width>1 or height>1:
        width=max(1,width//2);height=max(1,height//2);result+=width*height
    return result


def mesh_counts(binary,text):
    zero,offset,size=struct.unpack_from('<III',binary)
    require(zero==0 and offset+size+12==len(binary),'Invalid native header')
    result=[]
    for match in NODE.finditer(text.split('endmodelgeom')[0]):
        faces=arrays(match[3],'faces')
        if not faces:continue
        needle=match[2].encode('ascii')+b'\0';candidates=[];name=binary.find(needle)
        while name>=0:
            node=name-32
            if node>=12 and node+0x264<=12+offset and struct.unpack_from('<I',binary,node+0x6c)[0]==33:
                candidates.append(node)
            name=binary.find(needle,name+1)
        require(len(candidates)==1,'Expected one typed native mesh; material names may repeat')
        node=candidates[0]
        face_offset,count,capacity=struct.unpack_from('<III',binary,node+0x78)
        vertices,channels=struct.unpack_from('<HH',binary,node+0x230)
        require(count==capacity==len(faces) and vertices>0 and channels==1
                and face_offset+count*32<=offset,'Native/ASCII mesh counts differ')
        result.append({'node':match[2],'vertices':vertices,'triangles':count})
    require(result,'No current native meshes')
    return result


def measure(converted,output):
    converted=Path(converted).resolve();output=Path(output).resolve()
    require(not output.exists(),'Fresh read-only cost receipt required')
    _,_,inventory=validate_effective_body(converted)
    resources=converted/'resources';rows=[]
    for name,pin in inventory['resourceHashes'].items():
        path=resources/name
        row={'name':name,'sha256':pin,'serializedBytes':path.stat().st_size}
        if path.suffix=='.mdl':
            row['meshes']=mesh_counts(path.read_bytes(),(converted/'ascii'/name).read_text())
        elif path.suffix=='.plt':
            data=path.read_bytes();layers,reserved,w,h=struct.unpack_from('<IIII',data,8)
            require(data[:8]==b'PLT V1  ' and layers==10 and reserved==0 and len(data)==24+2*w*h,
                    'Invalid palette texture')
            row.update(width=w,height=h,decodedShadeAndLayerBytes=w*h*2,
                       hypotheticalRecoloredRGBA8BaseBytes=w*h*4,
                       hypotheticalRecoloredRGBA8MipBytes=mip_pixels(w,h)*4)
        elif path.suffix=='.tga':
            with Image.open(path) as image:
                w,h=image.size
                row.update(width=w,height=h,storedImageMode=image.mode,
                           decodedImageBytes=w*h*len(image.getbands()),
                           hypotheticalRGBA8BaseBytes=w*h*4,
                           hypotheticalRGBA8MipBytes=mip_pixels(w,h)*4)
        rows.append(row)
    meshes=[m for row in rows for m in row.get('meshes',[])]
    textures=[row for row in rows if 'width' in row]
    result={'schemaVersion':1,'converted':str(converted),'inventorySha256':sha(converted/'effective-material-inventory.json'),
            'completeBodySelected':inventory['completeBodySelected'],'acceptedSixBytesExact':True,
            'resources':rows,'resourceCount':len(rows),'modelCount':len(inventory['modelParts']),
            'serializedPayloadBytes':sum(row['serializedBytes'] for row in rows),
            'nativeMeshCount':len(meshes),'nativeVertices':sum(row['vertices'] for row in meshes),
            'nativeTriangles':sum(row['triangles'] for row in meshes),
            'textureResourceCount':len(textures),
            'hypotheticalAllTextureRGBA8BaseBytes':sum(row.get('hypotheticalRGBA8BaseBytes',row.get('hypotheticalRecoloredRGBA8BaseBytes',0)) for row in textures),
            'hypotheticalAllTextureRGBA8MipBytes':sum(row.get('hypotheticalRGBA8MipBytes',row.get('hypotheticalRecoloredRGBA8MipBytes',0)) for row in textures),
            'uniqueTextureContentHashes':len({row['sha256'] for row in textures}),
            'memoryPolicy':'Per resource name, no speculative content deduplication. RGBA8 figures are an explicit hypothetical uncompressed allocation, not observed engine memory. Stock head/neck/rig, equipment, animation, driver/cache and framebuffer costs are excluded.',
            'clientPerformanceMeasured':False,'clientLaunchedByThisTool':False,
            'executedCodeSha256':sha(__file__)}
    save(output,result)
    print(json.dumps({key:result[key] for key in ['completeBodySelected','resourceCount','nativeVertices','nativeTriangles','serializedPayloadBytes','hypotheticalAllTextureRGBA8MipBytes']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--converted',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();measure(args.converted,args.output)
