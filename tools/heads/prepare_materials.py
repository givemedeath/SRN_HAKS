"""Convert reviewed 2K PBR maps and semantic mask into 1024 runtime maps.

The semantic mask is authored/reviewed separately (0 skin, 1 hair, 2 fixed).
Normal green transport is explicit and remains subject to native/client review.
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from head_workflow import pin, read, require, verify_pins, write_fresh


def image(path, mode, size):
    with Image.open(path) as value:
        require(value.size == (size,size), "Expected explicit square source resolution")
        return value.convert(mode)


def prepare(config_path, output):
    config=read(config_path)
    require(config["kind"]=="srn-head-materials" and config["maskReviewed"] is True,
            "Reviewed skin/hair/fixed semantic mask required")
    require(type(config["flipNormalGreen"]) is bool, "Explicit normal-map transport choice required")
    verify_pins(config["inputs"])
    consumed={str(Path(config[k]).resolve()) for k in ("baseColor","normal","roughness","semanticMask","skinPalette","hairPalette")}
    require(consumed <= {str(Path(p["path"]).resolve()) for p in config["inputs"]}, "Material input not declared")
    color=image(config["baseColor"],"RGB",2048).resize((1024,1024),Image.Resampling.LANCZOS)
    with Image.open(config['semanticMask']) as value:
        require(value.mode=='L' and value.size==(2048,2048),'Explicit 2K byte semantic mask required')
        original_mask=value.copy()
    require(set(np.unique(original_mask)) <= {0,1,2}, "Unknown semantic mask label")
    mask=np.asarray(original_mask.resize((1024,1024),Image.Resampling.NEAREST))
    require({0,1} <= set(np.unique(mask)), "Recolorable skin and hair coverage required")
    rgb=np.asarray(color,dtype=float)
    shades=np.zeros((1024,1024),dtype=np.uint8)
    for layer,key,selector in ((0,"skinPalette","skinRow"),(1,"hairPalette","hairRow")):
        with Image.open(config[key]) as value:
            palette=np.asarray(value.convert("RGB"),dtype=float)
        require(palette.shape[1:] == (256,3) and type(config[selector]) is int
                and 0<=config[selector]<len(palette), "Actual 256-shade palette row required")
        pixels=rgb[mask==layer]
        chosen=[]
        for chunk in np.array_split(pixels,max(1,(len(pixels)+4095)//4096)):
            chosen.extend(((chunk[:,None,:]-palette[config[selector]][None,:,:])**2).sum(2).argmin(1))
        shades[mask==layer]=chosen
    # Fixed eyes/metal use their own mesh group/diffuse map; their palette pixels
    # are irrelevant and assigned skin solely to satisfy PLT's supported labels.
    layers=np.where(mask==1,1,0).astype(np.uint8)
    normal=image(config["normal"],"RGB",2048).resize((1024,1024),Image.Resampling.BILINEAR)
    vector=np.asarray(normal,dtype=float)/127.5-1
    if config["flipNormalGreen"]: vector[:,:,1]*=-1
    lengths=np.linalg.norm(vector,axis=2)
    require(np.all(lengths>1e-4), "Undefined normal vector")
    normal=Image.fromarray(np.clip(np.rint((vector/lengths[:,:,None]+1)*127.5),0,255).astype(np.uint8))
    rough=image(config["roughness"],"L",2048).resize((1024,1024),Image.Resampling.BILINEAR)
    output=Path(output); require(not output.exists(),"Fresh material output required"); output.mkdir(parents=True)
    for name,value in (("color",color),("normal",normal),("roughness",rough),
                       ("shades",Image.fromarray(shades)),("layers",Image.fromarray(layers)),
                       ("semantic",Image.fromarray(mask))):
        value.save(output/(name+".png"))
    verify_pins(config["inputs"])
    write_fresh(output/"materials.json",{"kind":"srn-head-runtime-materials","config":pin(config_path),
        "outputs":[pin(p) for p in sorted(output.glob("*.png"))],"textureSize":1024,
        "flipNormalGreen":config["flipNormalGreen"],"nativeValidated":False,"clientValidated":False})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();prepare(args.config,args.output)
