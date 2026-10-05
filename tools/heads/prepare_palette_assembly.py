"""Decode actual palette bytes into offline head/body/neck comparison atlases."""
import argparse
from pathlib import Path
import struct
import numpy as np
from PIL import Image
from head_workflow import pin,read,require,verify_pins,write_fresh


def palette_image(path,skin,hair,skin_row,hair_row):
    data=Path(path).read_bytes();require(data[:8]==b'PLT V1  ','Native palette required')
    width,height=struct.unpack_from('<II',data,16);require(len(data)==24+width*height*2,'PLT payload dimensions differ')
    pixels=np.frombuffer(data,'u1',offset=24).reshape(height,width,2)[::-1]
    require(np.isin(pixels[:,:,1],[0,1]).all(),'Preview only skin/hair palette layers')
    return np.where((pixels[:,:,1]==1)[:,:,None],hair[hair_row][pixels[:,:,0]],skin[skin_row][pixels[:,:,0]])


def prepare(config_path,output):
    c=read(config_path);verify_pins(c['inputs']);assembly=read(c['assembly']['path'])
    output=Path(output);require(not output.exists(),'Fresh palette assembly required');output.mkdir(parents=True)
    skin=np.asarray(Image.open(c['skinPalette']).convert('RGB'));hair=np.asarray(Image.open(c['hairPalette']).convert('RGB'))
    for index,head in enumerate(assembly['heads']):
        model=c['models'][index];materials=Path(c['materials'][index]);native=Path(c['native'][index])
        rgb=palette_image(native/(model+'.plt'),skin,hair,c['skinRow'],c['hairRow'])
        semantic=np.asarray(Image.open(materials/'semantic.png'));fixed=np.asarray(Image.open(materials/'color.png').convert('RGB'))
        rgb[semantic==2]=fixed[semantic==2];path=output/(model+'.png');Image.fromarray(rgb).save(path)
        head['colorMap']=pin(path);head['normalMap']=pin(materials/'normal.png');head['roughnessMap']=pin(materials/'roughness.png')
    for i,part in enumerate(assembly['parts']):
        model=Path(part['source']['path']).stem
        path=Path(c['stock'])/(model+'.plt') if model=='pmh0_neck001' else Path(c['body'])/(model+'.plt')
        rgb=palette_image(path,skin,hair,c['skinRow'],c['hairRow']);destination=output/(model+f'-{i}.png')
        Image.fromarray(rgb).save(destination);part['colorMap']=pin(destination)
    assembly['palettePreview']={'skinRow':c['skinRow'],'hairRow':c['hairRow'],'config':pin(config_path),'nativeResourcesRead':True,'clientEvidence':False}
    write_fresh(output/'assembly.json',assembly);verify_pins(c['inputs'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();prepare(a.config,a.output)
