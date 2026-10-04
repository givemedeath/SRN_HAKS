"""Initialize shared master UV bindings before the exact stock-rig fitter."""
import argparse
import json
from pathlib import Path
from PIL import Image

def main():
    parser=argparse.ArgumentParser();parser.add_argument("converted",type=Path)
    args=parser.parse_args();root=args.converted.resolve()
    report=json.loads((root/"conversion.json").read_text())
    color=root/"textures/base-color.png";mask=root/"textures/body-no-hair.png"
    if Image.open(color).size!=(2048,2048):raise RuntimeError("Expected approved 2K source atlas")
    Image.new("L",(2048,2048),0).save(mask)
    report["partTextures"]={p["model"]:{"color":str(color),"hairMask":str(mask),"size":2048,
        "fixed":report["textures"]["fixed"],"sharedSourceAtlas":True}
        for p in report["parts"] if not p.get("stockHead") and not p.get("stockPart")}
    (root/"resources").mkdir(exist_ok=True)
    (root/"conversion.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
