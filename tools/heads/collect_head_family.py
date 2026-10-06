"""Extract installed head/neck controls for an explicit engine race family."""
import argparse
from pathlib import Path
import subprocess
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from tool_runtime import tool
from head_workflow import pin, require, write_fresh


def collect(game, user, prefix, output):
    require(prefix in ('pmh0','pmd0','pme0','pmo0','pmg0'), 'Explicit male family required')
    output=Path(output); require(not output.exists(), 'Fresh installed control bank required')
    raw=output/'raw'; ascii_dir=output/'ascii'; raw.mkdir(parents=True); ascii_dir.mkdir()
    game=Path(game).resolve(); user=Path(user).resolve()
    require(game.is_dir() and user.is_dir(), 'Explicit existing game/user roots required')
    cat=tool('nwn_resman_cat'); compiler=tool('mdlcomp'); files=[]
    names=[prefix+'_neck001.mdl',prefix+'_head001.mdl']; seen=set()
    for name in names:
        if name in seen: continue
        seen.add(name)
        result=subprocess.run([str(cat),'--root',str(game),'--userdirectory',str(user),'--no-ovr',name],capture_output=True)
        require(result.returncode==0, 'Installed extraction failed: '+result.stderr.decode('utf-8',errors='replace'))
        require(len(result.stdout)>32, 'Missing installed family control: '+name)
        target=raw/name; target.write_bytes(result.stdout); files.append(pin(target))
        if name.endswith('.mdl'):
            decoded=ascii_dir/name
            if result.stdout[:4]==b'\0\0\0\0':
                subprocess.run([str(compiler),'-d','-e',str(target),str(decoded)],capture_output=True,check=True)
            else: decoded.write_bytes(result.stdout)
            require('newmodel' in decoded.read_text(encoding='cp1252'), 'Invalid installed control')
            files.append(pin(decoded))
            names.extend(bitmap.lower()+'.plt' for bitmap in re.findall(r'(?mi)^\s*bitmap\s+(\S+)',decoded.read_text(encoding='cp1252')) if bitmap.lower()!='null')
    write_fresh(output/'collection.json',{'kind':'srn-head-family-controls','prefix':prefix,
        'origin':'Installed NWN game, no override resources','files':files,'clientValidated':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('game','user','prefix','output'): p.add_argument('--'+name,required=True)
    a=p.parse_args();collect(a.game,a.user,a.prefix,a.output)
