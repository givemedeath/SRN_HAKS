"""texturesheet.py HEAD STAGE ATTEMPT OUT.png: labeled diagnostic atlas/mask contact sheet; no approval."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
from headbatch.head_files import read, sha

def draw(head, stage, attempt, output):
    if stage not in ('paint','masks','tone') or not attempt.startswith('attempt-') or Path(attempt).name!=attempt:
        raise ValueError('Explicit paint/masks/tone attempt required')
    folder=Path(head)/'run'/stage/attempt
    receipt=read(folder/'receipt.json')
    if receipt.get('state')!='complete':raise ValueError('Complete attempt required')
    rows=[]
    for row in receipt.get('outputs',[]):
        path=Path(row['path'])
        if path.suffix.lower()=='.png' and path.is_relative_to(folder.resolve()):
            if sha(path)!=row['sha256']:raise ValueError('Attempt image changed: '+str(path))
            rows.append((path,row))
    if not rows:raise ValueError('No pinned attempt images')
    columns=min(3,len(rows));size=512;label=44
    sheet=Image.new('RGB',(columns*size,((len(rows)+columns-1)//columns)*(size+label)),(30,30,30))
    pen=ImageDraw.Draw(sheet)
    for i,(path,_) in enumerate(rows):
        x=i%columns*size;y=i//columns*(size+label)
        with Image.open(path) as source:
            dimensions=source.size
            image=source.convert('RGB');image.thumbnail((size,size),Image.Resampling.NEAREST if stage=='masks' else Image.Resampling.BOX)
            sheet.paste(image,(x,y+label))
        pen.text((x+6,y+4),f'{Path(head).name} {stage} {attempt}',fill='white')
        pen.text((x+6,y+20),f'{path.name} {dimensions} | diagnostic thumbnail',fill='white')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Sheet already exists')
    sheet.save(output)
    return output

if __name__=='__main__':print(draw(*sys.argv[1:]))
