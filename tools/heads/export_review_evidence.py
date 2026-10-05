"""Export compact offline review artifacts with portable hashes and provenance."""
import argparse
from pathlib import Path
import math
import re
import shutil
from PIL import Image,ImageDraw
from head_workflow import pin,read,require,sha,verify_pins,write_fresh


def export(config_path,output):
    c=read(config_path);require(c['kind']=='srn-head-review-evidence','Explicit evidence selection required')
    verify_pins(c['inputs']);output=Path(output);require(not output.exists(),'Fresh compact evidence directory required');output.mkdir(parents=True)
    sources=[]
    for row in c['copies']:
        require(re.fullmatch(r'[a-z0-9-]+\.(png|txt)',row['name']),'Invalid evidence name')
        verify_pins([row['source']]);shutil.copyfile(row['source']['path'],output/row['name'])
        sources.append({'asset':row['name'],'sourceSha256':row['source']['sha256']})
    for row in c['sheets']:
        require(re.fullmatch(r'[a-z0-9-]+\.png',row['name']) and row['images'],'Named selected sheet required')
        verify_pins([item['image'] for item in row['images']]);canvas=Image.new('RGB',(1280,350*math.ceil(len(row['images'])/4)),(245,245,245));draw=ImageDraw.Draw(canvas)
        for index,item in enumerate(row['images']):
            with Image.open(item['image']['path']) as original:
                value=original.convert('RGB');value.thumbnail((320,320),Image.Resampling.LANCZOS)
            x,y=index%4*320,index//4*350;canvas.paste(value,(x+(320-value.width)//2,y))
            draw.text((x+5,y+324),item['label'],fill=(20,20,20))
            sources.append({'asset':row['name'],'frame':index,'label':item['label'],'sourceSha256':item['image']['sha256']})
        canvas.save(output/row['name'])
    files=[{'path':'evidence/'+path.name,'sha256':sha(path),'bytes':path.stat().st_size} for path in sorted(output.iterdir())]
    require(all(p['bytes']<=15*1024*1024 for p in files),'Compact evidence exceeds file size policy')
    write_fresh(output/'manifest.json',{'kind':'srn-head-portable-review-evidence','files':files,'sourceHashes':sources,
        'origins':c['origins'],'clientEvidence':False,'productionAccepted':False})
    verify_pins(c['inputs'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();export(a.config,a.output)
