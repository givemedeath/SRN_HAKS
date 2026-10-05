"""Retain native stock PLT headers and audit model-named palette candidates."""
import argparse
import json
from pathlib import Path
import re
import struct
import numpy as np
from audit_geometry import arrays
from pipeline import digest, save_json
from retarget import NODE

FORMAT_SOURCE='https://nwn.wiki/spaces/NWN1/pages/14618045/PLT'
MATERIAL_SOURCE='https://nwn.wiki/pages/viewpage.action?pageId=129237010'


def read_stock_plt(blob):
    if len(blob)<24 or blob[:8]!=b'PLT V1  ':raise RuntimeError('Invalid stock PLT signature/header')
    unused1,unused2,width,height=struct.unpack_from('<IIII',blob,8)
    if not width or not height or len(blob)!=24+width*height*2:raise RuntimeError('Invalid stock PLT dimensions/payload length')
    pixels=np.frombuffer(blob,dtype=np.uint8,offset=24).reshape(height,width,2)
    if np.any(pixels[:,:,1]>9):raise RuntimeError('Invalid stock PLT material channel')
    channels={str(int(layer)):int(count) for layer,count in zip(*np.unique(pixels[:,:,1],return_counts=True))}
    return {'width':width,'height':height,'unusedHeaderDwords':[unused1,unused2],
            'materialChannelPixelCounts':channels,'shadeMinimum':int(pixels[:,:,0].min()),
            'shadeMaximum':int(pixels[:,:,0].max()),'bytes':len(blob)}


def audit(args):
    inventory=json.loads(args.inventory.read_text())
    deps={row['name']:row for row in inventory['dependencies']}
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    records=[]
    for row in inventory['models']:
        matches=row.get('unresolvedBitmapWithModelNamedPalette',[])
        if not matches:continue
        source=Path(row['asciiPath'])
        if digest(source)!=row['asciiSha256']:raise RuntimeError('Palette mesh source changed')
        blocks={block[2].lower():block for block in NODE.finditer(source.read_text(encoding='ascii').split('endmodelgeom')[0])}
        for match in matches:
            dep=deps[match['palette']];path=Path(dep['rawPath'])
            if digest(path)!=dep['sha256']:raise RuntimeError('Native palette source changed')
            plt=read_stock_plt(path.read_bytes())
            uv=np.asarray(arrays(blocks[match['node'].lower()][3],'tverts'))
            records.append({'resource':row['resource'],'node':match['node'],'declaredBitmap':match['bitmap'],
                            'sourceAsciiSha256':row['asciiSha256'],'nativePartPalette':match['palette'],
                            'nativePartPaletteSha256':dep['sha256'],'plt':plt,
                            'uvMinimum':uv[:,:2].min(0).tolist() if uv.size else None,
                            'uvMaximum':uv[:,:2].max(0).tolist() if uv.size else None,
                            'nativeHeaderAndPixelsPreserved':True,
                            'candidateResolution':'Use the exact installed model-named PLT under the target part resref; omit skin MTR texture0.',
                            'sourceType':'installed-native-part-palette','engineBindingAccepted':False,'clientAccepted':False})
    receipt={'schemaVersion':1,'kind':'stock-equipment-native-plt-evidence',
             'sourceInventory':{'path':str(args.inventory.resolve()),'sha256':digest(args.inventory)},
             'formatSource':FORMAT_SOURCE,'engineMaterialSource':MATERIAL_SOURCE,
             'formatObservation':'Header DWORDs at offsets8 and12 are unused; ten material channels are encoded per pixel.',
             'records':records,'models':len(set(row['resource'] for row in records)),
             'nativePartPalettesValid':True,'declaredBitmapMissing':True,'clientAccepted':False,
             'limitation':'Palette existence, valid format and retained UVs support a candidate resolution; literal client rendering still proves binding and color correctness.'}
    save_json(out/'palette-evidence.json',receipt)
    print(json.dumps({'models':receipt['models'],'meshBindings':len(records),'validNativePalettes':True,'clientAccepted':False}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','output'):parser.add_argument('--'+field,type=Path,required=True)
    audit(parser.parse_args())


if __name__=='__main__':main()
