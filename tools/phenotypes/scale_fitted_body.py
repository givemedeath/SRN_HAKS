"""Uniformly scale a fitted body without changing UVs, topology or stock rotations.

Only use a fresh destination with equipment/native outputs already removed.
Embedded GLB image, normal, index and UV bytes remain untouched. Retarget and
recalibrate equipment after this operation; historical fit receipts stay frozen.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np

from pipeline import digest, save_json, RACES, HEIGHT_TARGETS
from measure_stock_head_fit import measure


def read_glb(path):
    data=path.read_bytes()
    magic,version,total=struct.unpack_from("<III",data)
    if magic!=0x46546c67 or version!=2 or total!=len(data):
        raise RuntimeError("Expected a glTF 2 GLB")
    chunks=[];offset=12
    while offset<len(data):
        length,kind=struct.unpack_from("<II",data,offset);offset+=8
        chunks.append((kind,data[offset:offset+length]));offset+=length
    if [kind for kind,_ in chunks]!=[0x4e4f534a,0x004e4942]:
        raise RuntimeError("Expected embedded JSON and binary chunks")
    return json.loads(chunks[0][1]),bytearray(chunks[1][1])


def position_views(document,buffer):
    indices={primitive["attributes"]["POSITION"] for mesh in document["meshes"]
             for primitive in mesh["primitives"]}
    for index in sorted(indices):
        accessor=document["accessors"][index]
        if accessor["componentType"]!=5126 or accessor["type"]!="VEC3" or "sparse" in accessor:
            raise RuntimeError("Unsupported position accessor")
        view=document["bufferViews"][accessor["bufferView"]]
        if view.get("buffer",0)!=0:raise RuntimeError("External position buffer")
        offset=view.get("byteOffset",0)+accessor.get("byteOffset",0)
        stride=view.get("byteStride",12)
        array=np.ndarray((accessor["count"],3),dtype="<f4",buffer=buffer,
                         offset=offset,strides=(stride,4))
        yield index,array


def scale_glb(source,destination,factor):
    document,buffer=read_glb(source)
    count=0
    for index,points in position_views(document,buffer):
        points[:]=points*factor;count+=len(points)
        accessor=document["accessors"][index]
        accessor["min"]=points.min(0).tolist();accessor["max"]=points.max(0).tolist()
    for node in document.get("nodes",[]):
        if "translation" in node:node["translation"]=[v*factor for v in node["translation"]]
        if "matrix" in node:
            for index in (12,13,14):node["matrix"][index]*=factor
    packed=json.dumps(document,separators=(",",":")).encode()
    packed+=b" "*((-len(packed))%4)
    payload=struct.pack("<II",len(packed),0x4e4f534a)+packed
    payload+=struct.pack("<II",len(buffer),0x004e4942)+buffer
    destination.write_bytes(struct.pack("<III",0x46546c67,2,12+len(payload))+payload)
    return count


def scale_ascii(path,factor):
    text=path.read_text(encoding="ascii")
    def block(match):
        rows=match[2].splitlines()
        if len(rows)!=int(match[1]):raise RuntimeError("Malformed vertex block")
        return "  verts "+match[1]+"\n"+"".join(
            "    "+" ".join(f"{float(v)*factor:.9g}" for v in row.split())+"\n" for row in rows)
    text=re.sub(r"(?m)^\s*verts\s+(\d+)\s*\n((?:[ \t]+[-+.eE0-9]+[^\n]*\n)+)",block,text)
    text=re.sub(r"(?m)^([ \t]*position)[ \t]+([^\n]+)",
                lambda m:m[1]+" "+" ".join(f"{float(v)*factor:.9g}" for v in m[2].split()),text)
    path.write_text(text,encoding="ascii")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--baseline",type=Path,required=True)
    parser.add_argument("--slug",required=True)
    args=parser.parse_args();source=args.source.resolve();output=args.output.resolve()
    if output.exists():raise RuntimeError("Preserve previous candidates; use a fresh destination")
    original=json.loads((source/"conversion.json").read_text())
    if any((source/name).exists() for name in ("item-equipment.json","equipment-proof.json","native-compile.json")):
        raise RuntimeError("Remove stale equipment/native outputs before scaling")
    race,sex,_=args.slug.split("_");target=RACES[race]["height"][sex]
    factor=target/original["height"]
    frozen={str(p):digest(p) for p in [source/"conversion.json",Path(__file__).resolve(),
        Path(__file__).with_name("height_targets.json").resolve(),
        *sorted((source/"parts").glob("*.glb")),*sorted((source/"ascii").glob("*.mdl"))]}
    shutil.copytree(source,output)
    report=copy.deepcopy(original)
    snapshot=output/"code-snapshot/scale_fitted_body.py"
    snapshot.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(Path(__file__),snapshot)
    report.setdefault("codeSnapshots",{})[str(Path(__file__).resolve())]={"path":str(snapshot),"sha256":digest(snapshot)}
    calibration=measure(args.baseline.resolve())
    if abs(calibration["stockHeight"]-HEIGHT_TARGETS["stockMaleHumanHeight"])>1e-8:
        raise RuntimeError("Installed stock Human measurement differs from the height baseline")
    calibration_path=output.parent.parent/"stock-head-fit.json"
    save_json(calibration_path,calibration)
    report["height"]=target;report["bodyHeight"]*=factor
    for coords in report["jointWorldNwn"].values():coords[:]=[v*factor for v in coords]
    fit=report["operations"]["headlessTposeFit"]
    for key in ("bodyHeight","fullHeight","halfArmSpan","armBandZ","neckCentreY","headOffsetY"):
        fit[key]*=factor
    fit["stockScale"]*=factor
    fit["calibration"]=str(calibration_path);fit["calibrationSha256"]=digest(calibration_path)
    for section in fit["sectionMeasurements"]:
        section["value"]*=factor
        for key in ("minimum","maximum","centre"):section[key]=[v*factor for v in section[key]]
    for key in ("sourceRadii","stockRadii"):
        fit["neckCapFit"][key]=[v*factor for v in fit["neckCapFit"][key]]
    for key in ("baseZ","capZ"):fit["neckCapFit"][key]*=factor
    counts={}
    for path in sorted((source/"parts").glob("*.glb")):
        counts[path.name]=scale_glb(path,output/"parts"/path.name,factor)
    for entry in report["parts"]:
        scale_ascii(output/"ascii"/(entry["model"]+".mdl"),factor)
        if "stockHead" in entry:entry["stockHead"]["scale"]*=factor
    for texture in report["partTextures"].values():
        for key in ("color","hairMask"):
            path=Path(texture[key]).resolve()
            if not path.is_relative_to(source):raise RuntimeError("External current texture")
            texture[key]=str(output/path.relative_to(source))
    for name in ("surface-audit.json","shell-audit.json","retarget.json","textures.json"):
        (output/name).unlink(missing_ok=True)
    operation={"source":str(source),"frozenInputHashes":frozen,"factor":factor,
        "originalHeight":original["height"],"targetHeight":target,
        "originalFit":original["operations"]["headlessTposeFit"],
        "positionCounts":counts,"uvTopologyPreserved":True,"stockRotationControllersChanged":False,
        "codeSnapshot":{"path":str(snapshot),"sha256":digest(snapshot)},"clientAccepted":False}
    report["operations"]["uniformHeightScale"]=operation
    save_json(output/"conversion.json",report);save_json(output/"height-scaling.json",operation)
    root=output.parent.parent
    manifest=json.loads((source.parent.parent/"manifest.json").read_text())
    for record in manifest["combinations"]:
        if record.get("fixtureControl"):continue
        record["referenceHeightMeters"]=RACES[record["race"]]["referenceHeight"][record["gender"]]
        record["heightMeters"]=RACES[record["race"]]["height"][record["gender"]]
        record["heightBasis"]="stock-male-human-reference-relative"
    save_json(root/"manifest.json",manifest)
    save_json(root/"height-targets.json",HEIGHT_TARGETS)
    for path,expected in frozen.items():
        if digest(Path(path))!=expected:raise RuntimeError("Scale input changed: "+path)
    print(json.dumps({"slug":args.slug,"factor":factor,"targetHeight":target,"parts":len(counts)}))


if __name__=="__main__":main()
