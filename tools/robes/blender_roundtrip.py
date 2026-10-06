"""Import an ASCII model with Neverblender, export it unchanged, and re-import the export.

Runs inside the launcher's isolated Blender. Used for the stock control and for
re-import verification of candidates. Records object structure only; numerical
comparison happens in compare_skin_models.py. Approves nothing.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from robe_common import FLAGS, fresh_directory, pin, require, sha, utc, write_fresh

EXPORT = {"export_animations": False, "export_walkmesh": False, "export_normals": False,
          "export_smoothing_mode": "GROUP", "uv_merge": True, "uv_mode": "REN", "uv_order": "ACT",
          "apply_modifiers": True, "strip_trailing": False, "batch_mode": "OFF"}
IMPORT = {"anim_import": False, "import_geometry": True, "import_walkmesh": False, "import_normals": True,
          "import_smoothgroups": True, "mat_import": True, "tex_search": False}


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.armatures):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def summary():
    rows = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        row = {"name": obj.name, "type": obj.type, "parent": obj.parent.name if obj.parent else None,
               "meshtype": getattr(getattr(obj, "nvb", None), "meshtype", None),
               "matrixWorld": [list(map(float, r)) for r in obj.matrix_world]}
        if obj.type == "MESH":
            row.update(vertices=len(obj.data.vertices), polygons=len(obj.data.polygons),
                       vertexGroups=[g.name for g in obj.vertex_groups],
                       materials=[m.name for m in obj.data.materials if m],
                       uvLayers=[u.name for u in obj.data.uv_layers])
        rows.append(row)
    return rows


def load(path):
    clear()
    result = bpy.ops.scene.nvb_mdlimport(filepath=str(path), **IMPORT)
    require(result == {"FINISHED"}, "Neverblender import failed: " + str(path))
    return summary()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source = args.source.resolve()
    require(sha(source) == args.source_sha256, "Frozen source changed")
    output = fresh_directory(args.output)
    imported = load(source)
    name = source.stem
    require(name in bpy.data.objects, "Model root object missing after import: " + name)
    root = bpy.data.objects[name]
    for obj in bpy.data.objects:
        obj.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    exported = output / "exported" / source.name
    exported.parent.mkdir()
    result = bpy.ops.scene.nvb_mdlexport(filepath=str(exported), **EXPORT)
    require(result == {"FINISHED"} and exported.is_file(), "Neverblender export failed")
    require(sha(source) == args.source_sha256, "Import/export mutated the frozen source")
    reimported = load(exported)
    module = sys.modules["neverblender"]
    report = {"schemaVersion": 1, "kind": "srn-robe-neverblender-roundtrip", "createdUtc": utc(),
              "source": pin(source), "exported": pin(exported),
              "sideFiles": [pin(p) for p in sorted(exported.parent.iterdir()) if p != exported],
              "blenderVersion": bpy.app.version_string, "neverblenderVersion": list(module.bl_info["version"]),
              "loadedAddon": pin(module.__file__), "importOptions": IMPORT, "exportOptions": EXPORT,
              "imported": imported, "reimported": reimported, **FLAGS}
    print(json.dumps(write_fresh(output / "roundtrip.json", report)))


if __name__ == "__main__":
    main()
