"""Exact-attempt decoded iris crops beside source appearance and alternative runtime rows."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from headkit.runner import Runner
from headkit.common import pin,verify,write,require
from headkit.quality import focus_view
from headkit.face_masks import sample
from headkit.palette import rows_for_shades


def candidates(rgb,layers,shades,palette,current):
    selected=layers==8
    if not selected.any():return [],[]
    ranked=rows_for_shades(rgb[selected],shades[selected],palette[:176],keep=8)
    return list(dict.fromkeys([int(current)]+[row['row'] for row in ranked])),ranked


def run(head,attempt):
    head=Path(head);runner=Runner(head/'manifest.json',head/'bindings.json',head/'run')
    result=runner.result('palette',require_review=False);receipt=runner.state['stages']['palette']
    require(Path(receipt['path']).parent.name==attempt,'Iris comparison needs the current exact palette attempt')
    tone=runner.result('tone');masks=runner.result('masks');color=tone.get('maps',{}).get('1024')
    folder=head/'review-evidence'/('irisrows-'+attempt);number=1
    while folder.exists():number+=1;folder=head/'review-evidence'/f'irisrows-{attempt}-{number:02d}'
    folder.mkdir(parents=True)
    base={'kind':'headbatch-runtime-iris-comparison-v1','attempt':attempt,'stageReceipt':receipt,'approved':False}
    if color is None or '8' not in result['rows']:
        report={**base,'skipped':'No 1K source appearance or iris channel'};write(folder/'report.json',report,fresh=True);print(report['skipped']);return report
    paths={k:runner.input(role) for k,role in runner.data['palette']['inputs'].items()}
    inputs=[receipt,runner.state['stages']['tone'],runner.state['stages']['masks'],color,result['ownership'],result['shades'],masks['source'],*masks['files'].values(),*[pin(p) for p in paths.values()],pin(__file__)]
    verify(inputs,fresh=True)
    rgb=np.array(Image.open(color['path']).convert('RGB'));layers=np.array(Image.open(result['ownership']['path']));shades=np.array(Image.open(result['shades']['path']))
    tables={k:np.array(Image.open(p).convert('RGBA')) for k,p in paths.items()}
    choices,ranked=candidates(rgb,layers,shades,tables['8'],result['rows']['8'])
    if not choices:
        report={**base,'inputs':inputs,'skipped':'No mapped iris texels'};write(folder/'report.json',report,fresh=True);print(report['skipped']);return report
    region=focus_view(masks['source']['path'],masks,layers);xy=region['pts'][[468,473]]
    require(np.isfinite(xy).all(),'Invalid iris landmarks');lo=np.floor(xy.min(0)-[50,25]).astype(int);hi=np.ceil(xy.max(0)+[50,25]).astype(int)
    def crop(atlas):
        front=np.clip(sample(region['view'],atlas,region['uv']),0,255).astype(np.uint8)
        return Image.fromarray(front).crop((*lo,*hi)).resize((420,150))
    sheet=Image.new('RGB',(840,190*((len(choices)+2)//2)),(30,30,30));draw=ImageDraw.Draw(sheet)
    sheet.paste(crop(rgb),(0,25));draw.text((10,7),'Source appearance (unchanged)',fill='white')
    for j,row in enumerate(choices,1):
        decoded=np.zeros(rgb.shape,np.uint8)
        for layer in np.unique(layers):
            selected=layers==layer;chosen=row if layer==8 else result['rows'][str(layer)]
            decoded[selected]=tables[str(layer)][chosen,shades[selected],:3]
        x=(j%2)*420;y=(j//2)*190;sheet.paste(crop(decoded),(x,y+25));draw.text((x+8,y+7),'iris row '+str(row)+(' CURRENT' if row==result['rows']['8'] else ''),fill='white')
    out=folder/'sheet.png';sheet.save(out);verify(inputs,fresh=True)
    report={**base,'inputs':inputs,'rows':choices,'ranking':ranked,'sheet':pin(out),'requiresVisualReview':True}
    write(folder/'report.json',report,fresh=True);print(out);return report


if __name__=='__main__':run(sys.argv[1],sys.argv[2])
