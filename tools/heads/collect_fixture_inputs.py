"""Extract installed stock templates and floor resources for an isolated fixture."""
import argparse
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from tool_runtime import tool
from head_workflow import pin,read,require,write_fresh


def collect(game,user,output):
    output=Path(output); require(not output.exists(),'Fresh fixture input bank required'); output.mkdir(parents=True)
    cat=tool('nwn_resman_cat'); gff=tool('nwn_gff'); files=[]
    for name in ('ttr01.set','ttr01_edge.2da','nw_humanmerc001.utc','x2_helm_001.uti','x2_helm_002.uti'):
        data=subprocess.run([str(cat),'--root',str(game),'--userdirectory',str(user),'--no-ovr',name],check=True,capture_output=True).stdout
        path=output/name; path.write_bytes(data); require(len(data)>32,'Empty stock resource'); files.append(pin(path))
        if path.suffix in ('.utc','.uti'):
            target=path.with_suffix(path.suffix+'.json')
            subprocess.run([str(gff),'-i',str(path),'-o',str(target)],check=True,capture_output=True)
            files.append(pin(target)); document=read(target)
            require(document['__data_type'] in ('UTC ','UTI '),'Unexpected stock template kind')
    write_fresh(output/'inputs.json',{'kind':'srn-head-fixture-stock-inputs','origins':'Installed game; stock templates only, no consumer modifications','files':files})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('game','user','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(); collect(a.game,a.user,a.output)
