import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import apply, cuts, detail, geometry, inventory

WALK = """node aabb walk
  parent t_a01
  position 0.0 0.0 0.0
  orientation 0.0 0.0 0.0 0.0
  bitmap NULL
  verts 4
    -5 -5 {z}
    5 -5 {z}
    5 5 {z}
    -5 5 {z}
  faces 2
    0 1 2 1 0 0 0 4
    0 2 3 1 0 0 0 4
  aabb -5 -5 {z} 5 5 {z} -1
    -5 -5 {z} 5 5 {z} 0
    -5 -5 {z} 5 5 {z} 1
endnode
"""
MODEL = """newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
  parent NULL
endnode
node trimesh roof
  parent t_a01
  position 0.0 0.0 {z}
  orientation 0.0 0.0 0.0 0.0
  bitmap roof_tex
  verts 3
    -5 -5 0
    5 -5 0
    5 5 0
  tverts 1
    0 0 0
  faces 1
    0 1 2 1 0 0 0 1
endnode
""" + WALK + """endmodelgeom t_a01
donemodel t_a01
"""
WOK = '# a walkmesh\n' + WALK.replace('parent t_a01', 'parent t_a01_pwk')
PIECE = """newmodel box
beginmodelgeom box
node dummy box
  parent NULL
endnode
node trimesh body
  parent box
  position 0.0 0.0 0.5
  orientation 0.0 0.0 1.0 1.5707963
  bitmap kit_atlas
  verts 4
    -0.5 -0.4 -0.5
    0.5 -0.4 -0.5
    0.5 0.4 0.5
    -0.5 0.4 0.5
  tverts 1
    0 0 0
  faces 2
    0 1 2 1 0 0 0 1
    0 2 3 1 0 0 0 1
endnode
endmodelgeom box
donemodel box
"""
SET = "[GENERAL]\nName=t\n[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n"


def _repo(root, z=10.0):
    own = root / 'srn_t_t'; own.mkdir(); (root / 'srn_t_common').mkdir(); kit = root / 'kit'; kit.mkdir()
    (own / 't.set').write_text(SET, encoding='cp1252')
    (own / 't_a01.mdl').write_text(MODEL.format(z=z), encoding='cp1252'); (own / 't_a01.wok').write_text(WOK.format(z=z), encoding='cp1252')
    (kit / 'box.mdl').write_text(PIECE, encoding='cp1252')
    return own, kit


def _area(node, material):
    return sum(cuts._area(*[node.verts[index] for index in face[:3]]) for face in node.faces if face[7] == material)


class Geometry(unittest.TestCase):
    def test_a_node_s_vertices_are_moved_by_its_position_and_turned_by_its_orientation(self):
        _, _, nodes = geometry.parse(PIECE)
        (part,) = geometry.baked(nodes)
        corners = sorted((round(x, 3), round(y, 3), round(z, 3)) for x, y, z in part[1])
        self.assertEqual(corners[0], (-0.4, -0.5, 1.0))  # a quarter turn takes (-0.5, 0.4, 0.5) to (-0.4, -0.5), then up by the position
        self.assertEqual({round(z, 3) for _, _, z in part[1]}, {0.0, 1.0})

    def test_a_mesh_named_like_the_root_hangs_from_the_root_not_from_itself(self):
        twin = PIECE.replace('node trimesh body', 'node trimesh box')  # the mesh shares the model root's name, as some doors' do
        _, _, nodes = geometry.parse(twin)
        (part,) = geometry.baked(nodes)
        self.assertEqual({round(z, 3) for _, _, z in part[1]}, {0.0, 1.0})

    def test_a_piece_s_meshes_with_one_look_are_merged_into_one_node(self):
        _, _, nodes = geometry.parse(PIECE); parts = geometry.baked(nodes)
        self.assertEqual(len(geometry.merged(parts + parts)), 1)
        (look, verts, tverts, faces), = geometry.merged(parts + parts)
        self.assertEqual((len(verts), len(faces)), (8, 4)); self.assertEqual(faces[2][:3], (4, 5, 6))


class Detail(unittest.TestCase):
    def test_a_piece_on_the_walkable_roof_is_refused_unless_it_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _, kit = _repo(root)
            spec = {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [1.0, 1.0, 10.0]}]}}
            with self.assertRaisesRegex(ValueError, 'stands where a player walks'):
                detail.detail(root, spec, kit, root / 'out')
            self.assertFalse((root / 'out' / 't_a01.mdl').exists())

    def test_a_piece_above_head_height_is_added_without_touching_the_walkmesh(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root)
            spec = {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [1.0, 1.0, 13.0]}, {'piece': 'box', 'at': [-2.0, 1.0, 13.0], 'turn': 90}]}}
            told = detail.detail(root, spec, kit, root / 'out')
            self.assertEqual(told['t_a01'], {'pieces': 2, 'faces': 4, 'nodes': 1, 'cuts': 0})
            made = (root / 'out' / 't_a01.mdl').read_text(encoding='cp1252')
            self.assertIn('node trimesh t_a01_kit00', made); self.assertEqual(made.count('_kit'), 1)
            self.assertEqual(inventory.walk_hash(made), inventory.walk_hash((own / 't_a01.mdl').read_text(encoding='cp1252')))
            self.assertFalse((root / 'out' / 't_a01.wok').exists()); self.assertFalse((root / 'out' / cuts.WALK_CUTS).exists())

    def test_a_piece_leaving_the_cell_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _, kit = _repo(root)
            spec = {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [4.8, 0.0, 13.0]}]}}
            with self.assertRaisesRegex(ValueError, 'leaves the cell'):
                detail.detail(root, spec, kit, root / 'out')

    def test_a_blocking_piece_on_a_roof_is_raised_out_of_its_walkmesh_as_a_walled_block(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root)
            spec = {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [1.0, 1.0, 10.0], 'blocks': True}]}}
            told = detail.detail(root, spec, kit, root / 'out')
            self.assertEqual(told['t_a01']['cuts'], 1)
            model, wok = ((root / 'out' / name).read_text(encoding='cp1252') for name in ('t_a01.mdl', 't_a01.wok'))
            node, other = cuts._walk_node(model), cuts._walk_node(wok)
            self.assertEqual((node.verts, node.faces), (other.verts, other.faces))  # the model's walkmesh and the .wok agree
            self.assertAlmostEqual(_area(node, cuts.BLOCK), 0.8, places=3)  # the box's footprint, 1 by 0.8 turned a quarter (its walls have no area from above)
            block = [node.verts[index] for face in node.faces if face[7] == cuts.BLOCK for index in face[:3]]
            self.assertEqual({round(z, 3) for _, _, z in block}, {10.0, 11.0})  # raised to the box's top, walled down to the roof
            walls = [face for face in node.faces if face[7] == cuts.BLOCK and len({round(node.verts[index][2], 3) for index in face[:3]}) == 2]
            wall_area = sum(0.5 * sum(value ** 2 for value in [(b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]), (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
                                                               (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])]) ** 0.5
                            for a, b, c in ([node.verts[index] for index in face[:3]] for face in walls))
            self.assertAlmostEqual(wall_area, 3.6, places=3)  # all round the footprint (1 + 0.8 + 1 + 0.8 m), 1 m high
            self.assertAlmostEqual(_area(node, 4), 99.2, places=3)  # the rest of the roof keeps its material
            self.assertFalse([1 for face in node.faces for side in range(3) for index, vertex in enumerate(node.verts)
                              if index not in face[:3] and cuts._on(node.verts[face[side]], node.verts[face[(side + 1) % 3]], vertex)])  # no T-junction
            self.assertTrue(all(cuts._side(*[node.verts[index] for index in face[:3]]) > 0 for face in node.faces if face not in walls))  # every other face still faces up
            self.assertIn('t_a01_pwk', wok)  # the walkmesh file keeps its own header
            record = json.loads((root / 'out' / cuts.WALK_CUTS).read_text(encoding='utf-8'))['models']['t_a01']
            self.assertEqual(record['wokFrom'], hashlib.sha256((own / 't_a01.wok').read_bytes()).hexdigest())
            self.assertEqual(record['aabbTo'], inventory.walk_hash(model))

    def test_running_again_cuts_the_pack_s_walkmesh_not_its_own_cut(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root)
            spec = {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [1.0, 1.0, 10.0], 'blocks': True}]}}
            detail.detail(root, spec, kit, root / 'out'); first = (root / 'out' / 't_a01.mdl').read_bytes()
            detail.detail(root, spec, kit, root / 'out')
            self.assertEqual((root / 'out' / 't_a01.mdl').read_bytes(), first)
            spec['tiles']['t_a01'][0].update(blocks=False, at=[1.0, 1.0, 13.0])  # no blocking piece any more: the pack's walkmesh again
            detail.detail(root, spec, kit, root / 'out')
            self.assertEqual(inventory.walk_hash((root / 'out' / 't_a01.mdl').read_text(encoding='cp1252')), inventory.walk_hash((own / 't_a01.mdl').read_text(encoding='cp1252')))
            self.assertFalse((root / 'out' / 't_a01.wok').exists())
            self.assertEqual(json.loads((root / 'out' / cuts.WALK_CUTS).read_text(encoding='utf-8'))['models'], {})

    def test_blocking_pieces_go_on_roofs_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _, kit = _repo(root, z=0.0)
            spec = {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [1.0, 1.0, 0.0], 'blocks': True}]}}
            with self.assertRaisesRegex(ValueError, 'only on a roof'):
                detail.detail(root, spec, kit, root / 'out')

    def test_a_cut_reaching_the_cell_s_side_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _, kit = _repo(root)
            spec = {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [4.6, 0.0, 10.0], 'blocks': True}]}}  # the turned box reaches x = 5
            with self.assertRaisesRegex(ValueError, 'reaches the side of the cell'):
                detail.detail(root, spec, kit, root / 'out')

    def test_a_footprint_over_a_face_s_side_splits_both_faces_alike(self):
        walk = cuts.Walkmesh([(-5, -5, 10), (5, -5, 10), (5, 5, 10), (-5, 5, 10)], [(0, 1, 2, 1, 0, 0, 0, 4), (0, 2, 3, 1, 0, 0, 0, 4)])
        self.assertEqual(walk.cut(cuts.hull([(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]), 10.0, 11.0), 2)  # across the diagonal
        walk.mend()
        self.assertAlmostEqual(sum(cuts._area(*walk.corners(face)) for face in walk.faces if face[7] == cuts.BLOCK), 1.0, places=6)
        self.assertAlmostEqual(sum(cuts._area(*walk.corners(face)) for face in walk.faces if face[7] != cuts.BLOCK), 99.0, places=6)
        self.assertFalse([1 for face in walk.faces for side in range(3) for index, vertex in enumerate(walk.verts)
                          if index not in face[:3] and cuts._on(walk.verts[face[side]], walk.verts[face[(side + 1) % 3]], vertex)])


class ApplyCuts(unittest.TestCase):
    def test_apply_replaces_a_walkmesh_only_as_the_cut_record_says_and_updates_the_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root)
            (root / 'hakbuilder.json').write_text(json.dumps({'HakList': [{'Name': 'srn_t_t'}, {'Name': 'srn_t_common'}], 'ExpectedOverrides': []}), encoding='utf-8')
            baseline = root / 'docs' / 'tilesets' / 't'; baseline.mkdir(parents=True)
            (baseline / 'walkmesh.json').write_text(json.dumps({'schemaVersion': 1, 'tileset': 't', 'models': {'t_a01': {'wok': 'old', 'aabb': 'old'}}}), encoding='utf-8')
            spec = {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [1.0, 1.0, 10.0], 'blocks': True}]}}
            detail.detail(root, spec, kit, root / 'out')
            record = json.loads((root / 'out' / cuts.WALK_CUTS).read_text(encoding='utf-8'))
            tampered = dict(record); tampered['models'] = {'t_a01': {**record['models']['t_a01'], 'wokTo': '0' * 64}}
            (root / 'out' / cuts.WALK_CUTS).write_text(json.dumps(tampered), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'replaced only as walk-cuts.json records'):
                apply.apply(root, None, root / 'out')
            (root / 'out' / cuts.WALK_CUTS).write_text(json.dumps(record), encoding='utf-8')
            told = apply.apply(root, None, root / 'out')
            self.assertEqual(told['put'], 2); self.assertEqual(told['not applied'], [])
            self.assertEqual((own / 't_a01.wok').read_bytes(), (root / 'out' / 't_a01.wok').read_bytes())
            entry = json.loads((baseline / 'walkmesh.json').read_text(encoding='utf-8'))['models']['t_a01']
            self.assertEqual(entry, {'wok': record['models']['t_a01']['wokTo'], 'aabb': record['models']['t_a01']['aabbTo'], 'cut': 1})

    def test_a_changed_walkmesh_without_a_record_is_still_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root)
            (root / 'hakbuilder.json').write_text(json.dumps({'HakList': [{'Name': 'srn_t_t'}], 'ExpectedOverrides': []}), encoding='utf-8')
            detail.detail(root, {'tileset': 't', 'tiles': {'t_a01': [{'piece': 'box', 'at': [1.0, 1.0, 10.0], 'blocks': True}]}}, kit, root / 'out')
            (root / 'out' / cuts.WALK_CUTS).unlink()
            with self.assertRaisesRegex(ValueError, 'walkmesh differs from the pack copy'):
                apply.apply(root, None, root / 'out')


if __name__ == '__main__':
    unittest.main()
