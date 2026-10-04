"""Create a fixture-only stock Human alias alongside overridden Human assets.

Uses a private dynamic family X and a new appearance row. Stock model surfaces,
PLTs and the installed stock supermodel remain unchanged apart from names.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

from pipeline import digest, save_json
from measure_stock_head_fit import measure


def stock_palette(text, baseline, palette_bank=None):
    """Resolve the model's bitmap, which may differ from its part/style name."""
    bitmaps={name.lower() for name in re.findall(r'(?mi)^\s*bitmap\s+(\S+)',text)
             if name.lower()!='null'}
    if len(bitmaps)!=1:raise RuntimeError('Stock comparator requires one actual palette bitmap')
    bitmap=next(iter(bitmaps)); candidates=[baseline/'raw'/(bitmap+'.plt')]
    if palette_bank:candidates.append(palette_bank/(bitmap+'.plt'))
    present=[path for path in candidates if path.is_file()]
    if not present:raise RuntimeError('Missing actual stock bitmap palette: '+bitmap)
    if len({digest(path) for path in present})!=1:raise RuntimeError('Ambiguous actual stock palette: '+bitmap)
    return bitmap,present[0]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--baseline",type=Path,default=Path("output/phenotypes/baseline"))
    parser.add_argument('--palette-bank',type=Path,help='Supplemental installed actual bitmap PLTs; existing stock bank remains immutable')
    args=parser.parse_args()
    slug="stock_human_male_fit"
    stock_height=measure(args.baseline)["stockHeight"]
    converted=args.output/slug/"converted"
    if converted.exists():raise RuntimeError("Stock control already exists")
    ascii_dir=converted/"ascii";resources=converted/"resources"
    ascii_dir.mkdir(parents=True);resources.mkdir()
    receipt=[]
    for part in ["","head","neck","chest","pelvis","bicepl","bicepr","forel","forer",
                 "handl","handr","legl","legr","shinl","shinr","footl","footr","belt","shol","shor"]:
        source_name="pmh0"+("_"+part+"001" if part else "")
        alias_name=source_name.replace("pmh0","pmx0")
        source=args.baseline/"ascii"/(source_name+".mdl")
        original=source.read_text(encoding="cp1252")
        text=original.replace("pmh0","pmx0")
        # Dynamic part PLT lookup is model-named. Bind the private alias's
        # corresponding original PLT, including mirrored right-hand parts.
        if part:
            text=re.sub(r"(?mi)^\s*bitmap\s+\S+", "  bitmap "+alias_name, text)
        target=ascii_dir/(alias_name+".mdl")
        target.write_text(text,encoding="cp1252")
        bitmap,plt=stock_palette(original,args.baseline,args.palette_bank) if part else (None,None)
        if plt:shutil.copyfile(plt,resources/(alias_name+".plt"))
        receipt.append({"source":str(source.resolve()),"sourceSha256":digest(source),"aliasSha256":digest(target),
                        "paletteSha256":digest(plt) if plt else None,
                        "sourceBitmap":bitmap,"paletteSource":str(plt.resolve()) if plt else None})
    appearance=(args.baseline/"raw/appearance.2da").read_text(encoding="cp1252")
    rows=[line.split() for line in appearance.splitlines() if re.match(r"^\s*\d+\s",line)]
    columns=next(line.split() for line in appearance.splitlines() if "MODELTYPE" in line)
    human=next(row for row in rows if row[0]=="6")[1:]
    row_id=max(int(row[0]) for row in rows)+1
    if len(human)!=len(columns):raise RuntimeError("Unexpected appearance column count")
    for key,value in {"LABEL":"SR_StockBodyControl","STRING_REF":"****","RACE":"X"}.items():
        human[columns.index(key)]=value
    fixture=args.output/"fixture-resources";fixture.mkdir(exist_ok=True)
    (fixture/"appearance.2da").write_text(appearance.rstrip()+"\n"+str(row_id)+" "+" ".join(human)+"\n",encoding="cp1252")
    manifest_path=args.output/"manifest.json"
    manifest=json.loads(manifest_path.read_text())
    manifest["combinations"].append({"slug":slug,"appearance":row_id,"raceId":6,"gender":"male", "phenotype":0,
                                    "fixtureControl":True,"height":stock_height,"race":"Stock Human","body_type":"Fit"})
    save_json(manifest_path,manifest)
    save_json(converted/"conversion.json",{"modelPrefix":"pmx0","height":stock_height,"parts":[],"textures":{},
              "geometryStatus":"stock-control","fixtureControl":True,"stockAliases":receipt})
    print(json.dumps({"slug":slug,"appearance":row_id,"models":len(receipt),"fixtureOnly":True}))


if __name__=="__main__":main()
