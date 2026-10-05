"""Lay out byte-pinned full-body evidence images without changing source captures."""
import argparse
import base64
import html
import json
from pathlib import Path
import shutil

from PIL import Image,ImageDraw,ImageFont
from stage_stock_part import require,sha,save
from effective_body_contract import validate_effective_body

REQUIRED={'idle','walk','run','cast','combat','crouch','kneel','death'}


def checked_config(path):
    record=json.loads(path.read_text())
    require(record['evidenceKind'] in ('offline-controller','nwn-ee-client'),
            'Offline and actual client evidence require distinct sheets')
    require(record.get('packagePins') and record.get('cases'),'Pinned package and frames required')
    converted=Path(record['effectiveBodyConverted']).resolve()
    _,_,inventory=validate_effective_body(converted)
    require(inventory['completeBodySelected'] is True,
            'Final full-body sheet requires all fourteen selected native parts')
    inventory_path=converted/'effective-material-inventory.json'
    inventory_pins=[pin for name,pin in record['packagePins'].items()
                    if Path(name).resolve()==inventory_path]
    require(inventory_pins and all(pin==sha(inventory_path) for pin in inventory_pins),
            'Reference sheet must pin its actual complete native inventory')
    require(REQUIRED<={row['category'] for row in record['cases']},'Full-body sheet missing animation categories')
    pins=dict(record['packagePins'])
    for row in record['cases']:
        require(row.get('fullBodyReviewed') is True and row.get('caption'),
                'Every full-body frame must be visually reviewed and captioned')
        pins[row['image']]=row['imageSha256'];pins[row['receipt']]=row['receiptSha256']
        if 'captureCrop' in row:
            require(record['evidenceKind']=='nwn-ee-client', 'Capture crops are only for actual client sheets')
            crop=row['captureCrop']
            require(isinstance(crop,list) and len(crop)==4 and all(type(v) is int for v in crop),
                    'Capture crop must contain four integer pixel bounds')
            with Image.open(row['image']) as source:
                require(0<=crop[0]<crop[2]<=source.width and 0<=crop[1]<crop[3]<=source.height,
                        'Capture crop must stay inside its original image')
    for source,pin in pins.items():require(sha(source)==pin,'Reference evidence changed: '+source)
    return record,pins


def build(config,output):
    require(not output.exists(),'Fresh reference-sheet output required')
    record,pins=checked_config(config);columns=4;cell_width=600;cell_height=740
    rows=(len(record['cases'])+columns-1)//columns;header=132
    font_path=Path('C:/Windows/Fonts/segoeui.ttf')
    require(font_path.is_file(),'Expected installed document font')
    output.mkdir(parents=True)
    heading=ImageFont.truetype(str(font_path),34);label=ImageFont.truetype(str(font_path),23)
    caption=ImageFont.truetype(str(font_path),17)
    canvas=Image.new('RGB',(columns*cell_width,header+rows*cell_height),(28,28,28));draw=ImageDraw.Draw(canvas)
    draw.text((28,18),record['title'],font=heading,fill=(245,245,245))
    description=('Actual NWN:EE client captures' if record['evidenceKind']=='nwn-ee-client'
                 else 'Offline stock-controller renders; client playback and lighting are separate evidence')
    draw.text((28,66),description,font=label,fill=(215,215,215))
    package_text='Package: '+', '.join(Path(p).name+' '+h[:12] for p,h in record['packagePins'].items())
    draw.text((28,102),package_text,font=caption,fill=(190,190,190))
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas.width}" height="{canvas.height}" viewBox="0 0 {canvas.width} {canvas.height}">',
         f'<rect width="100%" height="100%" fill="#1c1c1c"/><g fill="#f5f5f5" font-family="Segoe UI,sans-serif">',
         f'<text x="28" y="49" font-size="34">{html.escape(record["title"])}</text>',
         f'<text x="28" y="88" font-size="23">{html.escape(description)}</text>',
         f'<text x="28" y="120" font-size="17">{html.escape(package_text)}</text>']
    cases=[]
    for index,row in enumerate(record['cases']):
        x=(index%columns)*cell_width;y=header+(index//columns)*cell_height
        with Image.open(row['image']) as original:
            image=original.convert('RGB')
            if 'captureCrop' in row:
                image=image.crop(tuple(row['captureCrop']))
                viewport=output/(str(index).zfill(2)+'-'+row['category']+'-literal-viewport.png')
                image.save(viewport)
                embedded=viewport.read_bytes();mime='image/png'
            else:
                embedded=Path(row['image']).read_bytes();mime=Image.MIME.get(original.format,'image/png')
            if 'captureCrop' in row:
                factor=min((cell_width-20)/image.width,(cell_height-96)/image.height)
                image=image.resize((round(image.width*factor),round(image.height*factor)),Image.Resampling.LANCZOS)
            else:
                image.thumbnail((cell_width-20,cell_height-96),Image.Resampling.LANCZOS)
            px=x+(cell_width-image.width)//2;py=y+42+(cell_height-100-image.height)//2
            canvas.paste(image,(px,py))
        draw.text((x+12,y+6),row['label'],font=label,fill=(245,245,245))
        require(len(row['caption'])<=82,'Keep each evidence caption readable')
        # Two intentionally bounded text lines; source image content is unchanged.
        words=row['caption'].split();lines=['']
        for word in words:
            trial=(lines[-1]+' '+word).strip()
            if draw.textlength(trial,font=caption)>cell_width-24:lines.append(word)
            else:lines[-1]=trial
        require(len(lines)<=2,'Caption needs a shorter label')
        for line,text in enumerate(lines):draw.text((x+12,y+cell_height-45+21*line),text,font=caption,fill=(210,210,210))
        encoded=base64.b64encode(embedded).decode('ascii')
        svg.extend([f'<text x="{x+12}" y="{y+30}" font-size="23">{html.escape(row["label"])}</text>',
                    f'<image x="{x+10}" y="{y+42}" width="{cell_width-20}" height="{cell_height-100}" preserveAspectRatio="xMidYMid meet" href="data:{mime};base64,{encoded}"/>'])
        for line,text in enumerate(lines):svg.append(f'<text x="{x+12}" y="{y+cell_height-27+21*line}" font-size="17">{html.escape(text)}</text>')
        case={**row,'cell':[x,y,cell_width,cell_height]}
        if 'captureCrop' in row:case.update({'literalViewport':str(viewport),'literalViewportSha256':sha(viewport)})
        cases.append(case)
    svg.append('</g></svg>')
    png=output/'animation-reference-sheet.png';canvas.save(png)
    vector=output/'animation-reference-sheet.svg';vector.write_text('\n'.join(svg),encoding='utf-8')
    shutil.copyfile(config,output/'config.json');shutil.copyfile(__file__,output/'executed-sheet-builder.py')
    for source,pin in pins.items():require(sha(source)==pin,'Reference source changed during layout')
    save(output/'reference-sheet.json',{'schemaVersion':1,'evidenceKind':record['evidenceKind'],
        'title':record['title'],'packagePins':record['packagePins'],'frozenInputs':pins,
        'effectiveBodyConverted':str(Path(record['effectiveBodyConverted']).resolve()),
        'completeBodySelected':True,
        'cases':cases,'pngSha256':sha(png),'svgSha256':sha(vector),'sourceCapturesModified':False,
        'layoutPolicy':'Uniform aspect-preserving letterbox layout; explicit client-only pixel crops preserve original captures and colors. No semantic editing or generative imagery.',
        'font':str(font_path),'fontSha256':sha(font_path),'executedCodeSha256':sha(__file__)})
    print(json.dumps({'sheet':str(png),'cases':len(cases),'evidenceKind':record['evidenceKind']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();build(args.config.resolve(),args.output.resolve())
