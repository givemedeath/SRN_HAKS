"""Compose explicitly selected evidence images into a compact review sheet."""
import argparse
from pathlib import Path
import math
from PIL import Image,ImageDraw
from head_workflow import pin,read,require,verify_pins,write_fresh


def compose(config,output):
    rows=read(config);verify_pins([row['image'] for row in rows])
    require(rows and not Path(output).exists(),'Selected images and fresh output required')
    width=4*320; canvas=Image.new('RGB',(width,math.ceil(len(rows)/4)*350),(245,245,245));draw=ImageDraw.Draw(canvas)
    for i,row in enumerate(rows):
        with Image.open(row['image']['path']) as original:
            image=original.convert('RGB');image.thumbnail((320,320),Image.Resampling.LANCZOS)
        x,y=(i%4)*320,(i//4)*350;canvas.paste(image,(x+(320-image.width)//2,y))
        draw.text((x+5,y+324),row['label'],fill=(20,20,20))
    canvas.save(output)
    write_fresh(Path(output).with_suffix('.json'),{'kind':'srn-head-review-sheet','selection':pin(config),'image':pin(output)})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();compose(a.config,a.output)
