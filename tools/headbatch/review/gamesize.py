"""Game-size palette and view sheet from an exact attempt, with optional candidate looks."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from headkit.runner import Runner
from headkit.common import write, pin, verify, require
from headkit.diagnostics import palette_sheet, pixels, sheet, views
from headkit.gltf import mesh


def candidate_sheet(source,shades_path,layers_path,palettes,rows,dll,output,choices):
    """Use the saved shade indices for every look and project the geometry only once."""
    require(len(choices)<=8,'Compare at most eight candidate looks at once')
    inputs=[pin(path) for path in (source,shades_path,layers_path,*palettes.values(),dll)]
    with Image.open(shades_path) as image: shades=np.array(image)
    with Image.open(layers_path) as image: layers=np.array(image)
    require(shades.shape==layers.shape and shades.ndim==2,'Matching PLT shade/layer maps required')
    masks={str(layer):layers==layer for layer in np.unique(layers)}
    require(masks.keys()<=palettes.keys() and masks.keys()<=rows.keys(),'Missing mapped palette channels')
    tables={}
    for channel in masks:
        with Image.open(palettes[channel]) as image: tables[channel]=np.array(image.convert('RGBA'))
    looks=[{'label':'chosen','rows':rows}]
    for choice in choices:
        require(choice and choice.keys()<=masks.keys(),'Candidate look needs mapped palette channels')
        label=' '.join(f'{channel}={row}' for channel,row in sorted(choice.items()))
        looks.append({'label':label,'rows':{**rows,**choice}})
    value=mesh(source);size=128
    names=('front','left-three-quarter','right-three-quarter','left-back-three-quarter','right-back-three-quarter')
    projected=list(views(value,dll,size,names));tiles=[]
    for look in looks:
        decoded=np.zeros((*layers.shape,3),np.uint8)
        for channel,mask in masks.items():
            row=look['rows'][channel];table=tables[channel]
            require(type(row) is int and 0<=row<min(176,len(table)),'Invalid stock palette row')
            colors=table[row,shades[mask]]
            require(np.all(colors[:,3]>0),'Candidate look would make saved shades transparent')
            decoded[mask]=colors[:,:3]
        tiles.extend((look['label']+'\n'+name,pixels(view,decoded,value['uv'])) for name,view in projected)
    output.mkdir(parents=True,exist_ok=False)
    image=sheet(tiles,output/'sheet.png',size,columns=len(names))
    verify(inputs,fresh=True)
    return {'inputs':inputs,'sheet':image,'looks':looks,'pixelSize':size,'views':list(names),
            'visualReviewRequired':True,'clientEquivalent':False,'usesSavedShades':True}

def run(head,attempt,looks=()):
    head=Path(head);runner=Runner(head/'manifest.json',head/'bindings.json',head/'run')
    result=runner.result('palette',require_review=False)
    receipt=runner.state['stages']['palette']
    require(Path(receipt['path']).parent.name==attempt,'Game-size sheet must name the current exact palette attempt')
    source=runner.source('uvMesh','unwrap','mesh')
    palettes={k:runner.input(role) for k,role in runner.data['palette']['inputs'].items()}
    embree=runner.bindings['embree'];verify([embree],fresh=True)
    folder=head/'review-evidence'/('gamesize-'+attempt);number=1
    while folder.exists():
        number+=1;folder=head/'review-evidence'/f'gamesize-{attempt}-{number:02d}'
    arguments=(source,result['shades']['path'],result['ownership']['path'],palettes,result['rows'],embree['path'],folder)
    result=candidate_sheet(*arguments,looks) if looks else palette_sheet(*arguments)
    result.update(stageReceipt=receipt,attempt=attempt)
    verify([receipt],fresh=True);write(folder/'stage.json',result,fresh=True)
    print(result['sheet']['path'])
    return result

def candidate_look(value):
    try:
        pairs = [item.split('=',1) for item in value.split(',')]
        rows = {channel: int(row) for channel,row in pairs}
        if len(rows)!=len(pairs) or not rows.keys()<={str(i) for i in range(10)} or any(not 0<=row<=175 for row in rows.values()):
            raise ValueError
    except ValueError as error:
        raise argparse.ArgumentTypeError('Use distinct CHANNEL=ROW pairs with rows from 0 to 175') from error
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('head')
    parser.add_argument('attempt')
    parser.add_argument('--look',action='append',type=candidate_look,default=[],help='candidate CHANNEL=ROW[,CHANNEL=ROW]')
    args=parser.parse_args()
    run(args.head,args.attempt,args.look)
