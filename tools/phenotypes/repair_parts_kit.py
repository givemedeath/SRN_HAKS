"""Apply narrowly scoped kit repairs with content-addressed backups.

Run with bundled Python. External kit writes need workspace approval from the
host; the user has explicitly authorized fixing the supplied kit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


STABLE_BOUNDARIES = '''def boundary_loops(bm):
    # Stable simple-ring traversal: reject complete branched components.
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    def vertex_key(vertex):
        return tuple(round(float(c), 9) for c in vertex.co) + (vertex.index,)
    edges = {edge for edge in bm.edges if edge.is_boundary}
    adjacency = {}
    for edge in edges:
        for vertex in edge.verts:
            adjacency.setdefault(vertex, []).append(edge)
    unused = set(edges)
    rings = []
    rejected = []
    while unused:
        first = min(unused, key=lambda e: tuple(sorted(vertex_key(v) for v in e.verts)))
        stack, component = [first], {first}
        while stack:
            edge = stack.pop()
            for vertex in edge.verts:
                for neighbour in adjacency[vertex]:
                    if neighbour not in component:
                        component.add(neighbour)
                        stack.append(neighbour)
        unused.difference_update(component)
        vertices = {v for e in component for v in e.verts}
        if any(len(adjacency[v]) != 2 for v in vertices):
            rejected.append({"edges": len(component), "vertices": len(vertices),
                             "reason": "branched or open boundary component"})
            continue
        start = min(vertices, key=vertex_key)
        vertex = min((e.other_vert(start) for e in adjacency[start]), key=vertex_key)
        previous, ring = start, [start]
        while vertex is not start:
            ring.append(vertex)
            following = next(e.other_vert(vertex) for e in adjacency[vertex]
                             if e.other_vert(vertex) is not previous)
            previous, vertex = vertex, following
        if len(ring) >= 3:
            rings.append(ring)
    if rejected:
        REPORT.setdefault("rejectedBoundaryComponents", []).extend(rejected)
        log(f"{len(rejected)} ambiguous boundary components left for topology repair")
    return rings


'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kit", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    path = args.kit / "tools/blender_split.py"
    before = path.read_text(encoding="utf-8")
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    replacements = [
        ('''        hub = bm.verts.new(centre)
        for i in range(len(ring)):''',
         '''        # Opposing part caps otherwise coincide exactly and z-fight.
        part_centre = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
        inward = part_centre - centre
        if inward.length > 1e-12:
            inward.normalize()
        hub = bm.verts.new(centre + inward * min(radius * .12, extent * .01))
        for i in range(len(ring)):'''),
        ('''                face = bm.faces.new((a, b, hub))''',
         '''                edge = next(e for e in a.link_edges if b in e.verts)
                neighbour = edge.link_faces[0] if edge.link_faces else None
                same_order = neighbour and any(l.vert is a and l.link_loop_next.vert is b
                                               for l in neighbour.loops)
                face = bm.faces.new((b, a, hub) if same_order else (a, b, hub))'''),
        ('''    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)''',
         '''    # Keep the source surface winding. Reorienting every open shell
    # after a cut can flip valid exterior surfaces; caps follow edge winding.
    bm.normal_update()
    bm.to_mesh(mesh)'''),
        ('''    bmesh.ops.delete(bm, geom=[f for i, f in enumerate(bm.faces) if per_face[i] != part],
                     context="FACES")
    bm.to_mesh(copy.data)''',
         '''    bmesh.ops.delete(bm, geom=[f for i, f in enumerate(bm.faces) if per_face[i] != part],
                     context="FACES")
    # Face deletion can leave unreferenced source vertices. Those corrupt
    # per-part bounds and cap-size decisions even though glTF drops them.
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(copy.data)'''),
        ('''def export(obj, out_dir, name, formats):
    bpy.ops.object.select_all(action="DESELECT")''',
         '''def export(obj, out_dir, name, formats):
    # BMesh cuts/caps may leave invalid or degenerate elements. Repair them
    # before the glTF exporter makes its own unreported temporary repair.
    before_counts = (len(obj.data.vertices), len(obj.data.polygons))
    if obj.data.validate(verbose=True, clean_customdata=False):
        log(f"{name}: repaired invalid mesh elements before export "
            f"{before_counts} -> {(len(obj.data.vertices), len(obj.data.polygons))}")
    bpy.ops.object.select_all(action="DESELECT")'''),
        ('''    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for obj in list(bpy.context.scene.objects):''',
         '''    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # glTF duplicates vertices at UV seams. Keep UVs on face loops but weld
    # coincident geometry before cutting; otherwise each atlas island looks
    # like a separate open shell and joint caps can be generated on UV seams.
    bm = bmesh.new()
    bm.from_mesh(body.data)
    coords = [v.co for v in bm.verts]
    extent = max(max(v[k] for v in coords) - min(v[k] for v in coords)
                 for k in range(3)) if coords else 1.0
    before_vertices = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=max(extent * 1e-7, 1e-9))
    welded = before_vertices - len(bm.verts)
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    if welded:
        log(f"welded {welded} coincident UV-seam vertices; loop UVs preserved")
    for obj in list(bpy.context.scene.objects):'''),
        ('''        ring = [start, vert]
        while True:''',
         '''        ring = [start, vert]
        closed = False
        while True:'''),
        ('''            if vert is start:
                break
            ring.append(vert)
        if len(ring) >= 3:
            loops.append(ring)''',
         '''            if vert is start:
                closed = True
                break
            ring.append(vert)
        # An open chain or a branch is not a ring. Fanning one creates invalid
        # or overlapping faces. Leave it open for explicit topology repair.
        if closed and len(ring) >= 3 and len(set(ring)) == len(ring):
            loops.append(ring)'''),
    ]
    after = before
    changes = []
    for index, (old, new) in enumerate(replacements):
        if index in (6,7) and "Stable simple-ring traversal" in after:
            continue
        if new in after:
            continue
        if after.count(old) != 1:
            raise RuntimeError(f"Kit repair {index} no longer matches uniquely; review its source")
        after = after.replace(old, new, 1)
        changes.append(index)
    if "Stable simple-ring traversal" not in after:
        after, count = re.subn(r"def boundary_loops\(bm\):.*?(?=def cap\(obj, pre_open\):)",
                              lambda _: STABLE_BOUNDARIES, after, flags=re.S)
        if count != 1:
            raise RuntimeError("Boundary traversal repair no longer matches uniquely")
        changes.append(8)
    old_note = 'note += f", {skipped} open rings left (too large to cap)"'
    new_note = 'note += f", {skipped} boundary rings left for topology review"'
    if old_note in after:
        after = after.replace(old_note, new_note)
        changes.append(9)
    if changes:
        backup = path.with_name(path.name + "." + original_hash[:12] + ".bak")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
        compile(after, str(path), "exec")
        path.write_text(after, encoding="utf-8", newline="\n")
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"path": str(path), "beforeSha256": original_hash,
               "afterSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "repairsApplied": changes,
               "repairs": ["sink opposing cap hubs to avoid coincident surfaces",
                           "orient caps opposite their neighboring surface edge",
                           "preserve source exterior face winding",
                           "remove unreferenced vertices after face extraction",
                           "validate and report invalid geometry before export",
                           "weld UV-seam geometry while preserving loop UVs", "track closed boundary rings",
                           "cap only closed simple rings", "deterministic traversal rejecting branched components",
                           "describe skipped rings without assuming a size failure"]}
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
