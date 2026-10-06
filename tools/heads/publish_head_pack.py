"""Publish accepted resources and register their pack without production tables."""
import argparse
from pathlib import Path
from head_workflow import Session,pin,read,require,sha,write_fresh


def publish(session_root,identities,repository,manifest_path, *, slot_audit=None):
    session=Session(session_root);repo=Path(repository).resolve();config_path=repo/'hakbuilder.json'
    config=read(config_path);configuration_pin=pin(config_path)
    require(not any(p['Name']=='srn_head' for p in config['HakList']),'Head pack is already registered; explicit revision required')
    require(not Path(manifest_path).exists(),'Fresh publication manifest required')
    # All gates and ownership are checked before either repository mutation.
    session.publication(identities, slot_audit=slot_audit, repository=repo)
    publication=session.publish(identities,repo/'srn_head', slot_audit=slot_audit, repository=repo)
    require(sha(config_path)==configuration_pin['sha256'],'HAK configuration changed during publication')
    config['HakList'].append({'Name':'srn_head','Path':'./srn_head/','CompileModels':False})
    import json
    text=json.dumps(config,indent=2,allow_nan=False)+'\n'
    temporary=config_path.with_suffix('.json.tmp');temporary.write_text(text,encoding='utf-8')
    require(sha(config_path)==configuration_pin['sha256'],'HAK configuration changed before registration')
    temporary.replace(config_path)
    write_fresh(manifest_path,{**publication,'hakConfiguration':{'path':'hakbuilder.json','sha256':sha(config_path)}})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--design',action='append',required=True)
    parser.add_argument('--repository',type=Path,required=True);parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--slot-audit',type=Path,required=True)
    args=parser.parse_args();publish(args.session,args.design,args.repository,args.manifest, slot_audit=args.slot_audit)
