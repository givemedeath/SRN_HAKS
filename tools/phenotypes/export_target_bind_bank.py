"""Expose audited private-chain bind ownership for equipment-local skin audits.

These frames describe private supermodels only. Equipment model overrides must
be explicitly included by their separate converter; a similarly named core bone
is never substituted automatically.
"""
import argparse
import json
from pathlib import Path
import re

from retarget import nodes
from rig_controller_audit import effective_nodes, world_frames
from audit_target_rig import find_bind
from target_contract import load, sha, require


def export(candidate):
    contract_path=candidate/'target-contract.json';contract=load(contract_path)
    rig_receipt=json.loads((candidate/'rig-export.json').read_text())
    aliases=contract['rig']['privateAliases']
    result={'schemaVersion':1,'kind':'private-rig-bind-frame-bank',
        'targetContractSha256':sha(contract_path),'rigRevision':contract['rig']['revision'],
        'pilotAccepted':False,'equipmentProfilesAccepted':False,
        'ownershipPolicy':'Resolve equipment-model overrides explicitly before nearest private supermodel owner; reject unresolved bones.',
        'spaces':{}}
    for space in ('working','runtime'):
        texts={alias:(candidate/space/'ascii'/(alias+'.mdl')).read_text() for alias in aliases.values()}
        geometry={alias:nodes(text) for alias,text in texts.items()}
        parents={alias:re.search(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',text)[1].lower()
                 for alias,text in texts.items()}
        for pin in rig_receipt['models']:
            if pin['space']==space:
                require(sha(candidate/space/'ascii'/(pin['model']+'.mdl'))==pin['sha256'],
                        'Private model differs from rig export receipt')
        fallback=geometry[aliases['pmh0']]
        result['spaces'][space]={}
        for source_name,alias in aliases.items():
            effective=effective_nodes(alias,geometry,parents,fallback)
            world=world_frames(effective)
            bank={}
            for key,row in effective.items():
                _,owner=find_bind(key,alias,geometry,parents,fallback)
                bank[key]={'owner':owner,'parent':row['parent'],
                    'position':row['position'].tolist(),'orientation':row['orientation'],
                    'worldFrame':world[key].tolist()}
            result['spaces'][space][source_name]={'privateModel':alias,
                'sourcePrivateModelSha256':sha(candidate/space/'ascii'/(alias+'.mdl')),
                'nodes':bank}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists(),'Fresh bind bank receipt required')
    result=export(args.candidate.resolve())
    result['exportHelperSha256']=sha(Path(__file__))
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'path':str(args.output.resolve()),'sha256':sha(args.output),
        'models':len(result['spaces']['runtime']),'pilotAccepted':False}))
