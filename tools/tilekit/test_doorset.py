import re
import unittest

import numpy as np

from tools.tilekit import doorset, geometry, material

EMPTY = '1093        alien_door3        111925 vmr_gdoor03    1          1            4            111925\n' + ''.join(
    f'{row} ****                   ****   ****         ****       ****         ****         ****\n' for row in range(1094, 1110))


def _anims(text):
    return {match.group(1): match.group(2) for match in re.finditer(r'newanim (\w+) \w+\n(.*?)doneanim', text, re.S)}


class DoorSetTest(unittest.TestCase):
    def test_every_door_has_the_pack_doors_nodes_and_animations(self):
        for model in doorset.DOORS:
            text = doorset.model_text(model); _, root, nodes = geometry.parse(text); names = {node.name for node in nodes}
            self.assertEqual(root, model); self.assertLessEqual(len(model), 16)
            self.assertIn('classification Door', text)
            self.assertTrue({'sam', *(f'{model}{suffix}' for suffix in ('grnd', 'impc', 'hhit', 'head'))} <= names, model)
            anims = _anims(text)
            self.assertEqual(set(anims), {'opening1', 'opened1', 'closing1', 'opening2', 'opened2', 'closing2', 'closed', 'die', 'dead', 'trans'})
            for name, body in anims.items():  # every node in every animation, as the pack's doors list them
                self.assertEqual(set(re.findall(r'node \w+ (\S+)', body)), names, (model, name))
            self.assertIn('event 0.0333 detonate', anims['die'])

    def test_a_door_fills_its_whole_opening_and_draws_its_own_atlas(self):
        self.assertLessEqual(len(doorset.ATLAS), material.STEM); self.assertEqual(len(doorset.LOOKS), 16)
        for model, (_, width, _, _, _, _) in doorset.DOORS.items():
            _, _, nodes = geometry.parse(doorset.model_text(model))
            points = np.array([point for tri in geometry.triangles(nodes, lambda node: node.name != 'sam') for point in tri])
            height = doorset.TALL.get(model, doorset.HEIGHT)
            self.assertAlmostEqual(points[:, 0].min(), -width / 2, delta=0.12, msg=model); self.assertAlmostEqual(points[:, 0].max(), width / 2, delta=0.12, msg=model)
            self.assertAlmostEqual(points[:, 2].min(), 0.0, delta=0.01, msg=model); self.assertAlmostEqual(points[:, 2].max(), height, delta=0.01, msg=model)
            self.assertLess(np.abs(points[:, 1]).max(), 0.25, model)  # nothing reaches out into the street or the room but the shutter box
            self.assertTrue(all(f'bitmap {doorset.ATLAS}' == line.strip() for line in doorset.model_text(model).splitlines() if line.strip().startswith('bitmap') and 'NULL' not in line))

    def test_a_mirrored_leaf_faces_out(self):
        found = doorset.parts('srn_dr_double'); normals = []
        for name, flip in (('srn_dr_double_leaf1', np.array([-1.0, 1.0, 1.0])), ('srn_dr_double_leaf2', np.ones(3))):
            leaf = found[name][1]; verts = np.array(leaf.verts)
            normals.append([np.cross(verts[b] - verts[a], verts[c] - verts[a]) * flip for a, b, c, *_ in leaf.faces])
        np.testing.assert_allclose(normals[0], normals[1], atol=1e-9)  # each face of the other leaf faces as its mirror image does

    def test_walkmeshes_block_the_doorway_closed_and_clear_it_open(self):
        for model, (_, width, kind, _, _, _) in doorset.DOORS.items():
            text = doorset.walkmesh_text(model); meshes = {}
            for match in re.finditer(r'node trimesh \S+_DWK_(wg_\w+)\n(.*?)endnode', text, re.S):
                rows = re.search(r'verts \d+\n((?:\s+\S+ \S+ \S+\n)+)', match.group(2)).group(1)
                meshes[match.group(1)] = np.array([[float(value) for value in line.split()] for line in rows.strip().splitlines()])
                self.assertTrue(all(line.split()[-1] == '7' for line in match.group(2).split('faces')[1].strip().splitlines()[1:]), model)  # NonWalk
            self.assertEqual(set(meshes), {'wg_closed', 'wg_open1', 'wg_open2'})
            self.assertAlmostEqual(np.ptp(meshes['wg_closed'][:, 0]), width, places=3)
            for name, way in (('wg_open1', -1), ('wg_open2', 1)):
                points = meshes[name]
                if kind in ('swing', 'double'):  # a leaf turned out of the doorway, the way that state opens
                    self.assertAlmostEqual(way * points[:, 1].max() if way > 0 else -points[:, 1].min(), width / (2 if kind == 'double' else 1), delta=0.05, msg=(model, name))
                else:  # slivers at the jambs, the doorway clear
                    self.assertFalse(((np.abs(points[:, 0]) < width / 2 - 0.15)).any(), (model, name))
            self.assertEqual(len(re.findall(r'node dummy \S+_DWK_dp_', text)), 4)

    def test_rows_go_into_the_empty_rows_and_refuse_a_used_one(self):
        written = doorset.table(EMPTY).split('\n')
        self.assertIn('alien_door3', written[0])
        self.assertEqual([line.split()[3] for line in written[1:11]], list(doorset.DOORS))
        self.assertEqual(written[11].split()[1:], ['****'] * 7)
        self.assertEqual(written[8].split()[4], '0')  # the gate does not block sight
        self.assertEqual(doorset.table('\n'.join(written)), '\n'.join(written))  # written again: the same
        with self.assertRaises(ValueError):
            doorset.table(EMPTY.replace('1096 ****                   ****', '1096 somebody_else          1234', 1))
        self.assertTrue(doorset.table(EMPTY.replace('\n', '\r\n')).count('\r\n') == EMPTY.count('\n'))


if __name__ == '__main__':
    unittest.main()
