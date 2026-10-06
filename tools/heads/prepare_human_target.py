"""Measure the accepted Human male body's preserved stock neck/head frame.

Creates an unapproved contract proposal. A reviewer must explicitly approve its
envelope and landmark tolerance before fitting; other races remain pending.
"""
import argparse
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"phenotypes"))
from retarget import nodes
from rig_controller_audit import world_frames
from prepare_effective_body_preview import mesh_corners
from head_workflow import pin, read, require, sha, write_fresh


def prepare(body_manifest, repository, stock, output):
    manifest=read(body_manifest); repository=Path(repository).resolve(); stock=Path(stock).resolve()
    require(manifest["kind"]=="published-validated-human-male-body" and manifest["stockNeckHeadPreserved"] is True,
            "Accepted Human male publication preserving stock rig and neck required")
    for resource in manifest["resources"]:
        require(sha(repository/resource["path"])==resource["sha256"], "Accepted body publication changed")
    root=stock/"ascii/pmh0.mdl"; head=stock/"ascii/pmh0_head001.mdl"; neck=stock/"ascii/pmh0_neck001.mdl"
    frames=world_frames(nodes(root.read_text(encoding="cp1252")))
    points=np.concatenate([m["position"].reshape(-1,3) for m in mesh_corners(head.read_text(encoding="cp1252"))])
    palette=[stock/"raw/pal_skin01.tga",stock/"raw/pal_hair01.tga"]
    baseline=read(stock/"baseline.json")
    chain=[]; current="pmh0"
    while current!="null":
        require(current not in chain,"Stock animation chain cycle")
        chain.append(current); current=baseline["animations"][current]["supermodel"]
    proposal={"schemaVersion":1,"kind":"srn-head-target","race":"human","sex":"male","prefix":"pmh0",
        "phenotype":0,"bodyRevision":sha(body_manifest),"bodyManifest":pin(body_manifest),
        "bodyResourceRoot":str(repository),"rig":pin(root),"headBindMatrix":frames["head_g"].tolist(),
        "neckGeometry":pin(neck),"palettes":[pin(p) for p in palette],
        "animations":[pin(stock/"ascii"/(name+".mdl")) for name in chain],
        "cranialEnvelope":[points.min(0).tolist(),points.max(0).tolist()],
        "landmarkTolerance":0.005,"approved":False,
        "measurementOrigin":pin(head),"limits":"Measured stock head envelope proposal; requires review before fitting. No rig/body modifications."}
    write_fresh(output,proposal)
    return proposal


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("body-manifest","repository","stock","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args(); prepare(args.body_manifest,args.repository,args.stock,args.output)
