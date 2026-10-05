"""Audit the user-declared installed game/repository stack and persist 200 slots."""
import argparse
from pathlib import Path
from head_workflow import allocate_slots, pin, read, require, write_fresh


def audit(installed, proof, hak_config, repository, roster, output, allocated):
    repository=Path(repository).resolve()
    require(read(proof)["Appearance_Head"]["type"] == "byte", "Installed BIC head BYTE proof required")
    config=read(hak_config)
    resources=list(read(installed)); inputs=[pin(installed),pin(proof),pin(hak_config)]
    packs=[]
    for pack in config["HakList"]:
        folder=(repository/pack["Path"]).resolve()
        require(folder.is_relative_to(repository) and folder.is_dir(), "Declared HAK source missing or outside checkout")
        files=sorted(path for path in folder.rglob("*") if path.is_file())
        require(bool(files), "Declared pack is empty")
        resources += [path.name for path in files]
        inputs += [pin(path) for path in files]
        packs.append({"name":pack["Name"],"resources":len(files)})
    audit={"schemaVersion":1,"kind":"srn-head-slot-audit","complete":True,
           "consumerScope":"installed-game-and-repository-packs","maximum":255,
           "engineRangeProof":pin(proof),"inputs":inputs,"resources":sorted(set(resources)),"packs":packs,
           "rangeMeaning":"NWN installed BIC Appearance_Head uses BYTE (0..255); pipeline reserves 0. Actual client selectability remains a separate gate."}
    result=allocate_slots(read(roster),resources,maximum=255)
    write_fresh(output,audit); write_fresh(allocated,result)
    return audit


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("installed","proof","hak-config","repository","roster","output","allocated"):
        parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args(); audit(args.installed,args.proof,args.hak_config,args.repository,args.roster,args.output,args.allocated)
