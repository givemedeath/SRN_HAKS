"""Correct and verify NWNArmory's affine output in rigid part coordinates.

NWNArmory translates both vertices and mesh-node positions. Dynamic parts
require one translation. Robe skin hierarchies need a different treatment.
"""
import re
import numpy as np
from retarget import NODE, nodes, transforms
from audit_geometry import arrays
from pipeline import digest


def correct_rigid(source, target, transform):
    original=source.read_text(encoding="ascii")
    text=target.read_text(encoding="ascii")
    before=digest(target)
    scale=np.array(transform["scale"])
    translation=np.array(transform["translate"])
    source_nodes=nodes(original)
    source_world=transforms(source_nodes)
    source_blocks=[m for m in NODE.finditer(original.split("endmodelgeom")[0]) if arrays(m[3],"verts")]
    target_blocks=[m for m in NODE.finditer(text.split("endmodelgeom")[0]) if arrays(m[3],"verts")]
    if len(source_blocks)!=len(target_blocks) or not source_blocks:
        raise RuntimeError("Rigid armory mesh inventory differs: "+source.name)
    if any(m[1].lower() not in ("trimesh","danglymesh") for m in source_blocks+target_blocks):
        raise RuntimeError("Skin/animated equipment requires its own retargeting: "+source.name)
    if [m[1].lower() for m in source_blocks]!=[m[1].lower() for m in target_blocks]:
        raise RuntimeError("Equipment mesh types changed: "+source.name)
    if "newanim" in original.lower():raise RuntimeError("Local animated equipment requires separate retargeting")
    root=re.search(r"(?mi)^newmodel\s+(\S+)",text)[1]
    source_root=re.search(r"(?mi)^newmodel\s+(\S+)",original)[1].lower()
    errors=[]
    replacements=[]
    for src,dst in zip(source_blocks,target_blocks):
        for block in (src,dst):
            local_scale=re.search(r"(?m)^\s*scale\s+(\S+)",block[3])
            if local_scale and abs(float(local_scale[1])-1)>1e-6:
                raise RuntimeError("Non-unit mesh node scale requires explicit handling: "+source.name)
        if src[1].lower()=="danglymesh":
            # A rigidly attached dangly chest still uses local spring motion.
            # Preserve the stock spring parameters and vertex constraints.
            for label in ("displacement","period","tightness"):
                a=re.search(r"(?m)^\s*"+label+r"\s+(\S+)",src[3])
                b=re.search(r"(?m)^\s*"+label+r"\s+(\S+)",dst[3])
                if not a or not b or float(a[1])!=float(b[1]):
                    raise RuntimeError("Dangly physics changed: "+source.name+" "+label)
            if arrays(src[3],"constraints")!=arrays(dst[3],"constraints"):
                raise RuntimeError("Dangly constraints changed: "+source.name)
        if source_nodes[src[2].lower()]["parent"]!=source_root:
            raise RuntimeError("Nested rigid equipment must be flattened explicitly: "+source.name)
        matrix=source_world[src[2].lower()]
        if not np.allclose(matrix[:3,:3],np.eye(3),atol=1e-6):
            raise RuntimeError("Rotated rigid source needs explicit transform handling: "+source.name)
        vertices=np.array(arrays(src[3],"verts"))
        actual=np.array(arrays(dst[3],"verts"))
        expected_raw=vertices*scale+translation
        if actual.shape!=expected_raw.shape or np.max(np.abs(actual-expected_raw))>1e-5:
            raise RuntimeError("NWNArmory vertex transform differs from profile: "+source.name)
        position=matrix[:3,3]*scale
        body=re.sub(r"(?m)^\s*position\s+[^\n]+", "  position "+" ".join(f"{v:.9g}" for v in position),dst[3])
        if not re.search(r"(?m)^\s*position\s+",body):
            body+="  position "+" ".join(f"{v:.9g}" for v in position)+"\n"
        body=re.sub(r"(?m)^\s*parent\s+\S+", "  parent "+root,body)
        replacements.append((dst.start(),dst.end(),f"node {dst[1]} {dst[2]}\n{body}endnode"))
        errors.append(float(np.max(np.abs(actual+position-((vertices+matrix[:3,3])*scale+translation)))))
    for start,end,replacement in reversed(replacements):text=text[:start]+replacement+text[end:]
    text=re.sub(r"(?mi)^setsupermodel\s+\S+\s+\S+",f"setsupermodel {root} NULL",text)
    corrected_world=transforms(nodes(text))
    corrected_blocks=[m for m in NODE.finditer(text.split("endmodelgeom")[0]) if arrays(m[3],"verts")]
    errors=[]
    for src,dst in zip(source_blocks,corrected_blocks):
        vertices=np.array(arrays(src[3],"verts"));actual=np.array(arrays(dst[3],"verts"))
        expected=(vertices@source_world[src[2].lower()][:3,:3].T+source_world[src[2].lower()][:3,3])*scale+translation
        frame=corrected_world[dst[2].lower()]
        observed=actual@frame[:3,:3].T+frame[:3,3]
        errors.append(float(np.max(np.abs(observed-expected))))
    if max(errors)>1e-5:raise RuntimeError("Corrected assembled equipment differs from profile: "+source.name)
    target.write_text(text,encoding="ascii")
    return {"armoryOutputSha256":before,"correctedSha256":digest(target),
            "meshNodes":len(errors),"maximumWorldTransformError":max(errors),
            "meshTypes":[m[1].lower() for m in source_blocks],"danglyPhysicsPreserved":True,
            "method":"Keep affine vertices; scale source node positions without applying translation twice; rigid supermodel NULL"}
