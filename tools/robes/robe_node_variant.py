"""Write a structural variant of an ASCII robe model for client node-structure checks.

Stock skin robes (pmh0_robe003-006) carry their skeleton as render-0 trimesh
placeholders and have no hand, foot, shoulder or neck nodes. This tool swaps the
bone node kind (dummy <-> render-0 trimesh box) and can add stock skeleton nodes,
so a single difference can be tested in the client. Skin nodes, rest frames and
weights are copied unchanged. Writes <model>.mdl and variant.json; approves nothing.
"""
import argparse
from pathlib import Path
import shutil

import numpy as np

import mdl_ascii
from robe_common import FLAGS, pin, require, utc, verify_pins, write_fresh

# Stock robe004 rootdummy placeholder box, scaled to 4 cm.
BOX_VERTS = np.array([[1, -1, -1], [1, -1, 1], [-1, -1, 1], [-1, -1, -1],
                      [1, 1, -1], [-1, 1, -1], [-1, 1, 1], [1, 1, 1]], float) * 0.02
BOX_FACES = np.array([[0, 1, 2, 1, 0, 0, 0, 2], [2, 3, 0, 1, 0, 0, 0, 2], [4, 5, 6, 1, 0, 0, 0, 1],
                      [6, 7, 4, 1, 0, 0, 0, 1], [0, 3, 5, 2, 0, 0, 0, 5], [5, 4, 0, 2, 0, 0, 0, 5],
                      [3, 2, 6, 4, 0, 0, 0, 4], [6, 5, 3, 4, 0, 0, 0, 4], [2, 1, 7, 2, 0, 0, 0, 6],
                      [7, 6, 2, 2, 0, 0, 0, 6], [1, 0, 4, 4, 0, 0, 0, 3], [4, 7, 1, 4, 0, 0, 0, 3]])


def as_kind(node, kind):
    copy = mdl_ascii.Node(kind, node.name)
    copy.parent, copy.position, copy.orientation = node.parent, node.position.copy(), node.orientation.copy()
    if kind == "trimesh":
        if copy.orientation[3] == 0:
            copy.orientation = np.array([1.0, 0.0, 0.0, 0.0])
        copy.properties = [("ambient", "0.8 0.8 0.8"), ("diffuse", "0.5 0.6 1.0"), ("specular", "0.0 0.0 0.0"),
                           ("shininess", "26"), ("shadow", "0"), ("render", "0"), ("bitmap", "NULL")]
        copy.arrays = {"verts": BOX_VERTS.copy(), "faces": BOX_FACES.copy()}
    return copy


def variant(model, new_name, placeholders, add_nodes, stock, rename_bitmaps):
    old = model.name
    bones = [n for n in model.nodes if n.kind in ("dummy", "trimesh") and n.key != old.lower()]
    require(all(n.kind != "trimesh" or n.get("render", "1").strip() == "0" for n in bones),
            "Rendered trimesh nodes are not bone placeholders")
    present = set(model.names())
    for name in add_nodes:
        source = stock.node(name)
        require(source.parent.lower() in present, "Parent missing for added node " + name)
        require(source.key not in present, "Node already present: " + name)
        added = mdl_ascii.Node("dummy", source.name)
        added.parent, added.position, added.orientation = source.parent, source.position.copy(), source.orientation.copy()
        index = max(i for i, n in enumerate(model.nodes) if n.key == source.parent.lower()) + 1
        model.nodes.insert(index, added)
        present.add(added.key)
        bones.append(added)
    if placeholders != "keep":
        model.nodes = [as_kind(n, placeholders) if n in bones else n for n in model.nodes]
    model.name = new_name
    for node in model.nodes:
        if node.key == old.lower():
            node.name = new_name
        if node.parent.lower() == old.lower():
            node.parent = new_name
        if rename_bitmaps and node.kind in mdl_ascii.MESHES and (node.get("bitmap") or "").lower() == old.lower():
            node.set("bitmap", new_name)
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--model", required=True, help="New model resref")
    parser.add_argument("--placeholders", choices=["keep", "dummy", "trimesh"], default="keep")
    parser.add_argument("--add-node", action="append", default=[], help="Stock skeleton node to add as a dummy")
    parser.add_argument("--stock-model", type=Path, help="Stock skeleton model for --add-node")
    parser.add_argument("--rename-bitmaps", action="store_true", help="Point bitmaps naming the old model at the new one")
    parser.add_argument("--plt", type=Path, help="Skin PLT copied in as <model>.plt")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(len(args.model) <= 16, "Resref limit exceeded")
    require(not args.add_node or args.stock_model, "--add-node needs --stock-model")
    inputs = [pin(args.source)] + ([pin(args.stock_model)] if args.stock_model else [])
    output = Path(args.output).resolve()
    require(not output.exists(), "Fresh variant directory required")
    output.mkdir(parents=True)
    source = mdl_ascii.read(args.source)
    stock = mdl_ascii.read(args.stock_model) if args.stock_model else None
    model = variant(source, args.model, args.placeholders, args.add_node, stock, args.rename_bitmaps)
    path = output / (args.model + ".mdl")
    mdl_ascii.write(path, model)
    plt = None
    if args.plt:
        inputs.append(pin(args.plt))
        plt = output / (args.model + ".plt")
        shutil.copyfile(args.plt, plt)
    verify_pins(inputs)
    report = {"schemaVersion": 1, "kind": "srn-robe-node-variant", "createdUtc": utc(), "model": args.model,
              "placeholders": args.placeholders, "addedNodes": args.add_node, "renameBitmaps": args.rename_bitmaps,
              "nodes": [f"{n.kind} {n.name}" for n in model.nodes], "inputs": inputs, "file": pin(path),
              "plt": pin(plt) if plt else None, **FLAGS}
    print(write_fresh(output / "variant.json", report)["sha256"])


if __name__ == "__main__":
    main()
