"""Decode actual palette bytes into offline head/body/neck comparison atlases."""
import argparse
from pathlib import Path
import struct
import numpy as np
from PIL import Image
from head_workflow import pin,read,require,verify_pins,write_fresh


def palette_image(path,skin,hair,skin_row,hair_row,extra_layers=None):
    data=Path(path).read_bytes()
    require(len(data)>=24 and data[:8]==b'PLT V1  ','Native palette required')
    width,height=struct.unpack_from('<II',data,16)
    require(width>0 and height>0 and len(data)==24+width*height*2,'PLT payload dimensions differ')
    pixels=np.frombuffer(data,'u1',offset=24).reshape(height,width,2)[::-1]
    layers=pixels[:,:,1];require((layers<=9).all(),'PLT channel IDs must be 0..9')
    extra_layers=extra_layers or {}
    require(all(type(layer) is int and 2<=layer<=9 for layer in extra_layers),'Extra palette bindings must use channels 2..9')
    palettes={0:(skin,skin_row),1:(hair,hair_row),**extra_layers}
    rgb=np.empty((height,width,3),dtype=np.uint8)
    for layer in np.unique(layers):
        require(int(layer) in palettes,f'Missing palette binding for PLT channel {layer}')
        palette,row=palettes[int(layer)];palette=np.asarray(palette)
        require(palette.ndim==3 and palette.shape[1:]==(256,3)
                and type(row) is int and 0<=row<len(palette),f'Invalid palette/row for PLT channel {layer}')
        selected=layers==layer;rgb[selected]=palette[row][pixels[:,:,0][selected]]
    return rgb


def _as_path(item):
    return str(Path(item['path'] if isinstance(item, dict) else item).resolve())


def prepare(config_path,output):
    c=read(config_path);verify_pins(c['inputs'])
    declared={_as_path(p):p for p in c['inputs']}
    assembly=read(_as_path(c['assembly']))
    palette_layers=c.get('paletteLayers',{})
    require(isinstance(palette_layers,dict),'paletteLayers must map channel IDs to palette/row bindings')
    for layer,binding in palette_layers.items():
        require(layer in tuple(map(str,range(2,10))) and isinstance(binding,dict)
                and set(binding)=={'palette','row'},'Extra palette bindings need channel 2..9, palette and row')
    consumed=[c['assembly'],c['skinPalette'],c['hairPalette']]
    consumed.extend(binding['palette'] for binding in palette_layers.values())
    for index in range(len(assembly.get('heads',[]))):
        model=c['models'][index];materials=Path(c['materials'][index]);native=Path(c['native'][index])
        consumed.extend([native/(model+'.plt'),
                         materials/'semantic.png',materials/'color.png',
                         materials/'normal.png',materials/'roughness.png'])
    for part in assembly.get('parts',[]):
        if 'source' in part:consumed.append(part['source'])
        model=Path(_as_path(part['source'])).stem
        if part.get('joint')=='neck_g':
            consumed.append(Path(c.get('neckPalette',str(Path(c['stock'])/(model+'.plt')))))
        else:
            consumed.append(Path(c['body'])/(model+'.plt'))
    for item in consumed:
        target=_as_path(item)
        require(target in declared,f'Consumed source omitted from declaration: {target}')
        if isinstance(item,dict) and 'sha256' in item:
            require(declared[target]['sha256']==item['sha256'],'Declared pin hash mismatch')
    verify_pins([declared[_as_path(item)] for item in consumed])
    output=Path(output);require(not output.exists(),'Fresh palette assembly required');output.mkdir(parents=True)
    skin=np.asarray(Image.open(_as_path(c['skinPalette'])).convert('RGB'));hair=np.asarray(Image.open(_as_path(c['hairPalette'])).convert('RGB'))
    extra_layers={int(layer):(np.asarray(Image.open(_as_path(binding['palette'])).convert('RGB')),binding['row'])
                  for layer,binding in palette_layers.items()}
    for index,head in enumerate(assembly['heads']):
        model=c['models'][index];materials=Path(c['materials'][index]);native=Path(c['native'][index])
        rgb=palette_image(native/(model+'.plt'),skin,hair,c['skinRow'],c['hairRow'],extra_layers)
        semantic=np.asarray(Image.open(materials/'semantic.png'));fixed=np.asarray(Image.open(materials/'color.png').convert('RGB'))
        rgb[semantic==2]=fixed[semantic==2];path=output/(model+'.png');Image.fromarray(rgb).save(path)
        head['colorMap']=pin(path);head['normalMap']=pin(materials/'normal.png');head['roughnessMap']=pin(materials/'roughness.png')
    for i,part in enumerate(assembly['parts']):
        model=Path(_as_path(part['source'])).stem
        if part['joint']=='neck_g':
            path=Path(c.get('neckPalette',str(Path(c['stock'])/(model+'.plt'))))
        else: path=Path(c['body'])/(model+'.plt')
        rgb=palette_image(path,skin,hair,c['skinRow'],c['hairRow'],extra_layers);destination=output/(model+f'-{i}.png')
        Image.fromarray(rgb).save(destination);part['colorMap']=pin(destination)
    assembly['palettePreview']={'skinRow':c['skinRow'],'hairRow':c['hairRow'],'paletteLayers':{layer:{'palette':pin(_as_path(binding['palette'])),'row':binding['row']} for layer,binding in palette_layers.items()},'config':pin(config_path),'nativeResourcesRead':True,'clientEvidence':False}
    write_fresh(output/'assembly.json',assembly)
    verify_pins(c['inputs'])
    verify_pins([declared[_as_path(item)] for item in consumed])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();prepare(a.config,a.output)
