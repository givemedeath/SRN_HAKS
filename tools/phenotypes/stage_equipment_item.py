"""Stage all non-bare rigid styles used by an installed armor item.

The calibration and inputs are frozen in a receipt. Robes require a separate
skin/hierarchy path. Shared stock palette aliases become model-named palettes.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
from tool_runtime import tool as resolved_tool, record_dependencies

from pipeline import digest, save_json
from armory_rigid import correct_rigid
from baseline import COMPILER_SHA256

ARMOR_PARTS = {"Torso":"chest", "Pelvis":"pelvis", "Neck":"neck", "Belt":"belt",
    "LBicep":"bicepl", "RBicep":"bicepr", "LFArm":"forel", "RFArm":"forer",
    "LHand":"handl", "RHand":"handr", "LThigh":"legl", "RThigh":"legr",
    "LShin":"shinl", "RShin":"shinr", "LFoot":"footl", "RFoot":"footr",
    "LShoul":"shol", "RShoul":"shor"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--converted",type=Path,required=True)
    parser.add_argument("--template",type=Path,required=True)
    parser.add_argument("--profile-json",type=Path)
    parser.add_argument("--baseline",type=Path,required=True)
    parser.add_argument("--tool-directory",type=Path)
    parser.add_argument("--game-root",type=Path,required=True)
    parser.add_argument("--user-directory",type=Path,required=True)
    parser.add_argument("--armory",type=Path)
    parser.add_argument("--stock-identity",action="store_true",
                        help="Explicitly test unchanged stock male Human armor geometry at stock stature")
    args=parser.parse_args()
    converted=args.converted.resolve()
    frozen={}
    def freeze(path):
        path=path.resolve()
        value=digest(path)
        if path in frozen and frozen[path]!=value:
            raise RuntimeError("Equipment input changed: "+str(path))
        frozen[path]=value
        return value
    script_hash=freeze(Path(__file__))
    freeze(Path(__file__).with_name("armory_rigid.py"))
    template_hash=freeze(args.template)
    freeze(converted/"conversion.json")
    report=json.loads((converted/"conversion.json").read_text())
    prefix=report["modelPrefix"];source_prefix="p"+prefix[1]+"h0"
    item=json.loads(args.template.read_text())
    styles={part:int(item["ArmorPart_"+field]["value"]) for field,part in ARMOR_PARTS.items()
            if "ArmorPart_"+field in item and int(item["ArmorPart_"+field]["value"])>1}
    if item.get("ArmorPart_Robe",{}).get("value",0):raise RuntimeError("Robe requires separate skin retargeting")
    if not styles:raise RuntimeError("No non-bare equipment styles")
    profile=None
    if args.profile_json:
        freeze(args.profile_json)
        profile=json.loads(args.profile_json.read_text())
        ini=args.profile_json.parent/(profile["slug"]+".ini")
        args.armory=resolved_tool("armory", path=args.armory)
        if freeze(ini)!=profile["profileSha256"] or freeze(args.armory)!=profile["armorySha256"]:
            raise RuntimeError("NWNArmory/profile provenance mismatch")
        for transform in profile["transforms"].values():
            if "target" in transform and freeze(Path(transform["target"]))!=transform["targetSha256"]:
                raise RuntimeError("Calibration target changed")
            if "source" in transform and freeze(Path(transform["source"]))!=transform["sourceSha256"]:
                raise RuntimeError("Calibration source changed")
    elif not prefix[2]=="x":
        if not args.stock_identity or prefix!="pmh0" or abs(report["height"]-report.get("stockReferenceHeight",0))>1e-7:
            raise RuntimeError("Identity transform requires a stock-height male Human or private stock comparator")
    if args.stock_identity and profile:raise RuntimeError("Stock identity must not use an NWNArmory profile")
    for part,style in styles.items():
        name=prefix+"_"+part+f"{style:03}"
        if any(path.exists() for path in (converted/"ascii"/(name+".mdl"),
                converted/"resources"/(name+".mdl"),converted/"resources"/(name+".plt"))):
            raise RuntimeError("Equipment target already exists: "+part)
    directory=converted.parent/"item-equipment"
    directory.mkdir(exist_ok=False)
    source_dir=directory/"source";proof_dir=directory/"armory"
    source_dir.mkdir();proof_dir.mkdir()
    normalized=directory/"normalized";normalized.mkdir()
    raw=args.baseline/"raw";ascii_dir=args.baseline/"ascii"
    raw.mkdir(parents=True,exist_ok=True);ascii_dir.mkdir(exist_ok=True)
    def extract(name):
        path=raw/name
        if not path.exists():
            result=subprocess.run([str(resolved_tool("nwn_resman_cat", args.tool_directory)),"--root",str(args.game_root),
                "--userdirectory",str(args.user_directory),"--no-ovr",name],capture_output=True,check=True)
            if not result.stdout:raise RuntimeError("Missing resource: "+name)
            path.write_bytes(result.stdout)
        return path
    sources={}
    compiler=resolved_tool("mdlcomp")
    if freeze(compiler)!=COMPILER_SHA256:raise RuntimeError("Pinned model decompiler changed")
    for part,style in styles.items():
        name=source_prefix+"_"+part+f"{style:03}"
        source=ascii_dir/(name+".mdl")
        if not source.exists():
            binary=extract(name+".mdl")
            if binary.read_bytes()[:4]==b"\0\0\0\0":
                subprocess.run([str(compiler),"-d","-e",str(binary),str(source)],capture_output=True,check=True)
            else:shutil.copyfile(binary,source)
            if not source.exists() or "newmodel" not in source.read_text(encoding="ascii"):
                raise RuntimeError("Invalid decompiled equipment: "+name)
        source_hash=freeze(source)
        copied=source_dir/source.name
        shutil.copyfile(source,copied)
        if freeze(copied)!=source_hash:raise RuntimeError("Equipment copy differs from source")
        sources[part]=(source,copied)
    if profile:
        result=subprocess.run([str(args.armory.resolve()),str(ini.resolve()),str(source_dir),str(proof_dir)],capture_output=True,text=True,check=True)
        (directory/"armory.log").write_text(result.stdout+result.stderr)
        expected={prefix+source.stem[4:]+".mdl" for source,_ in sources.values()}
        if {p.name for p in proof_dir.iterdir()}!=expected:
            raise RuntimeError("NWNArmory batch inventory differs from the frozen selection")
    resources=[]
    for part,(original_source,source) in sources.items():
        name=prefix+source.stem[4:]
        target=normalized/(name+".mdl")
        if profile:
            proof=proof_dir/target.name
            if not proof.exists():raise RuntimeError("NWNArmory omitted "+name)
            shutil.copyfile(proof,target)
            transform=profile["transforms"][part]
        else:
            text=source.read_text(encoding="ascii")
            text=re.sub(r"(?i)\b"+re.escape(source.stem)+r"\b",name,text)
            target.write_text(text,encoding="ascii")
            transform={"scale":[1,1,1],"translate":[0,0,0]}
        check=correct_rigid(source,target,transform)
        # Dynamic part palette binding uses the part's resref. A stock model
        # may alias the opposite limb's PLT; preserve its actual palette data.
        stock_text=source.read_text(encoding="ascii")
        bitmaps=set(re.findall(r"(?mi)^\s*bitmap\s+(\S+)",stock_text))
        if len(bitmaps)!=1:raise RuntimeError("Multiple equipment textures need explicit dependency handling: "+source.name)
        bitmap=next(iter(bitmaps));palette=extract(bitmap+".plt")
        palette_hash=freeze(palette)
        text=target.read_text(encoding="ascii")
        text=re.sub(r"(?mi)^(\s*bitmap)\s+\S+",r"\g<1> "+name,text)
        target.write_text(text,encoding="ascii")
        shutil.copyfile(palette,normalized/(name+".plt"))
        if digest(normalized/(name+".plt"))!=palette_hash:raise RuntimeError("Equipment palette copy differs")
        resources.append({"part":part,"style":styles[part],"model":name,"stockSource":str(original_source.resolve()),
            "stockSourceSha256":frozen[original_source.resolve()],"stockPalette":bitmap,"paletteSha256":palette_hash,
            "asciiSha256":digest(target),"rigidTransformCheck":check})
    for path,value in frozen.items():
        if digest(path)!=value:raise RuntimeError("Equipment input changed before adoption: "+str(path))
    for path in normalized.iterdir():
        shutil.copyfile(path,converted/("ascii" if path.suffix==".mdl" else "resources")/path.name)
    save_json(converted/"item-equipment.json",{"templateSha256":template_hash,
        "dependencyReceipt":str(record_dependencies(frozen)),
        "fitMode":"stock-identity" if not profile else "nwnarmory-calibrated",
        "profileSha256":profile["profileSha256"] if profile else None,
        "profile":str(args.profile_json.resolve()) if profile else None,
        "armorySha256":digest(args.armory) if profile else None,
        "scriptSha256":script_hash,"frozenInputHashes":{str(p):v for p,v in frozen.items()},
        "resources":resources,"clientAccepted":False})
    print(json.dumps({"prefix":prefix,"styles":len(resources),"clientAccepted":False}))


if __name__=="__main__":main()
