"""Resolve a portable approved target through explicit ignored local bindings."""
import argparse
from pathlib import Path
from head_workflow import read,require,sha,validate_target,verify_pins,write_fresh


def bind(contract_path,binding_path,output):
    contract=read(contract_path);binding=read(binding_path)
    require(contract['kind']=='srn-head-portable-target' and contract['approved'] is True,'Approved portable contract required')
    require(binding['kind']=='srn-head-target-bindings','Explicit local contract bindings required')
    verify_pins(binding['inputs']);repo=Path(binding['repository']).resolve()
    def resolve(item):
        key=item['path']
        path=((repo/key).resolve() if key.startswith('docs/') else Path(binding['resources'][key]).resolve())
        if key.startswith('docs/'):require(path.is_relative_to(repo),'Publication path escapes repository')
        require(sha(path)==item['sha256'],'Target binding does not match approved pin: '+key)
        require(str(path) in {str(Path(p['path']).resolve()) for p in binding['inputs']},'Binding input not declared: '+key)
        return {'path':str(path),'sha256':item['sha256']}
    target={**contract,'kind':'srn-head-target','bodyResourceRoot':str(repo)}
    for key in ('bodyManifest','rig','neckGeometry'):target[key]=resolve(contract[key])
    for key in ('palettes','animations'):target[key]=[resolve(p) for p in contract[key]]
    validate_target(target);write_fresh(output,target)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('contract','binding','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();bind(args.contract,args.binding,args.output)
