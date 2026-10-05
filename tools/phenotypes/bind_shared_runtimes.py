"""Create a new ignored, immutable local runtime binding; never edit history."""
import argparse
from pathlib import Path
from shared_toolchain import resolve_runtime, tools_root
from shared_tools import write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python',type=Path,required=True)
    p.add_argument('--blender',type=Path)
    p.add_argument('--nwn',type=Path)
    p.add_argument('--tools-root',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[2]
    root,_=tools_root(repo,a.tools_root)
    runtimes={name:resolve_runtime(name,getattr(a,name),repo) for name in ('python','blender','nwn') if getattr(a,name)}
    write_json(a.output,{'schemaVersion':2,'kind':'phenotype-shared-toolchain',
        'toolsRoot':str(root),'runtimes':runtimes,'requiredTools':list(runtimes)},fresh=True)

if __name__=='__main__':main()
