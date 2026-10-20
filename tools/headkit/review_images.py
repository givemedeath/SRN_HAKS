"""CPU-only atlas derivatives and labeled review sheets for actual rendered images."""
from pathlib import Path
import time
from .common import require, pin, verify


def resolutions(config):
    require(not ('sizes' in config and 'size' in config), 'Choose review sizes or one diagnostic size')
    if 'size' in config:
        size=config['size']
        require(type(size) is int and 1<=size<=4096, 'Invalid diagnostic render size')
        return [size]
    sizes=config.get('sizes',[2048,1024])
    require(sizes==[2048,1024], 'Production review requires sizes [2048, 1024]')
    return sizes


def atlas_sets(config, output, sizes):
    """Use the actual mapped appearance; 1K views use actual BOX-filtered 1K atlases."""
    from PIL import Image
    output=Path(output);sets={};records=[]
    for size in sizes:
        maps={};folder=output/str(size)/'atlases';folder.mkdir(parents=True)
        for name,path in config.get('maps',{}).items():
            with Image.open(path) as source:
                require(source.width==source.height and source.width>=size, 'Review atlas must be square and large enough; no upsampling')
                image=source.convert('RGB' if name=='basecolor' else 'L')
                if image.size!=(size,size):image=image.resize((size,size),Image.Resampling.BOX)
                target=folder/(name+'.png');image.save(target)
            maps[name]=str(target);records.append({'size':size,'map':name,'source':pin(path),'image':pin(target)})
        sets[size]=maps
    return sets,records


def sheets(records, output, triangles):
    """Keep every source view at native resolution inside the labeled sheet."""
    from PIL import Image, ImageDraw
    output=Path(output);result=[];begun=time.monotonic()
    for size,mode in dict.fromkeys((row['size'],row['mode']) for row in records):
        views=[row for row in records if row['size']==size and row['mode']==mode]
        columns=min(3,len(views));rows=(len(views)+columns-1)//columns;label=32
        sheet=Image.new('RGB',(columns*size,rows*(size+label)),(30,30,30));draw=ImageDraw.Draw(sheet)
        for index,row in enumerate(views):
            verify([row['image']]);x=index%columns*size;y=index//columns*(size+label)
            with Image.open(row['image']['path']) as image:
                require(image.size==(size,size), 'Rendered frame dimensions differ from receipt')
                sheet.paste(image.convert('RGB'),(x,y+label))
            draw.text((x+8,y+8),f"{row['view']} | {mode} | {size}px | {triangles} triangles",fill='white')
        target=output/str(size)/(mode+'-sheet.png');sheet.save(target)
        result.append({'size':size,'mode':mode,'image':pin(target)})
    return {'sheets':result,'sheetSeconds':time.monotonic()-begun}
