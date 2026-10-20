"""CPU-only atlas derivatives and labeled review sheets for actual rendered images."""
from pathlib import Path
import time
import math
import re
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


def render_plan(config):
    cameras=config.get('cameras');modes=config.get('modes',['clay','color-only','material-lit'])
    require(isinstance(cameras,list) and cameras,'Render cameras must be a nonempty list')
    require(isinstance(modes,list) and modes and all(x in ('clay','color-only','material-lit') for x in modes)
            and len(set(modes))==len(modes),'Render modes must be nonempty, known and unique')
    require(type(config.get('diagnostic',False)) is bool,'Diagnostic render flag must be boolean')
    require(set(modes)=={'clay','color-only','material-lit'} or config.get('diagnostic') is True,
            'Production render plans require clay, color-only and material-lit; mark a reduced plan diagnostic explicitly')
    names=[]
    for view in cameras:
        require(isinstance(view,dict) and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*',view.get('name','')) is not None,
                'Safe camera name required')
        for field in ('eye','target'):
            require(isinstance(view.get(field),list) and len(view[field])==3 and all(type(x) in (int,float) and math.isfinite(x) for x in view[field]),
                    'Finite camera eye and target required')
        require(view['eye']!=view['target'] and type(view.get('orthoScale')) in (int,float)
                and math.isfinite(view['orthoScale']) and view['orthoScale']>0,'Valid camera scale and direction required')
        names.append(view['name'])
    require(len(set(names))==len(names),'Unique camera names required')
    return {(size,mode,name) for size in resolutions(config) for mode in modes for name in names}


def validate_frames(config,records):
    expected=render_plan(config)
    require(isinstance(records,list) and len(records)==len(expected)
            and {(row['size'],row['mode'],row['view']) for row in records}==expected,
            'Rendered frames do not cover the nonempty inspection plan')


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
