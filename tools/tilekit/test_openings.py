import unittest

from tools.tilekit import openings

WALK = """node aabb walk
  parent t
  verts 3
    -5 -5 0
    5 -5 0
    -5 5 0
  faces 1
    0 1 2 1 0 0 0 4
endnode
"""


def wall(name, material, axis, plane, low, high, bottom, top, parent='t'):
    spot = (lambda a, z: f'{plane} {a} {z}') if axis == 'x' else (lambda a, z: f'{a} {plane} {z}')
    return f"""node trimesh {name}
  parent {parent}
  bitmap {material}
  verts 4
    {spot(low, bottom)}
    {spot(high, bottom)}
    {spot(high, top)}
    {spot(low, top)}
  faces 2
    0 1 2 1 0 0 0 1
    0 2 3 1 0 0 0 1
endnode
"""


def model(*nodes):
    return 'newmodel t\nbeginmodelgeom t\nnode dummy t\n  parent NULL\nendnode\n' + ''.join(nodes) + 'endmodelgeom t\ndonemodel t\n'


SET = '[TILE7]\nModel=T\n[TILE7DOOR0]\nType=0\nX=0\nY=0\nZ=0\nOrientation=0\n[TILE7DOOR1]\nType=3\n[TILE8]\nModel=gone\n[TILE8DOOR0]\nType=0\n'
JAMBS = [wall('left', 'brick', 'x', -2, -1, 1, 0, 4), wall('right', 'brick', 'x', 1, -1, 1, 0, 4)]
LINTEL = 'node trimesh lintel\n  parent t\n  bitmap brick\n  verts 3\n    -3 -3 2.8\n    3 -3 2.8\n    0 3 2.8\n  faces 1\n    0 1 2 1 0 0 0 1\nendnode\n'


class OpeningsTest(unittest.TestCase):
    def test_a_doorway_between_its_jambs(self):
        text = model(*JAMBS, LINTEL, wall('t_kit00', 'kit', 'x', 0.4, -1, 1, 0, 4))  # a kit piece in the way is not a jamb
        found = openings.doorways(SET, {'t': text})
        self.assertEqual(found[0], {'tile': 7, 'model': 't', 'door': 0, 'at': [0, 0, 0], 'turn': 0, 'width': 3.0, 'height': 2.8, 'left': 1.0, 'right': 2.0})
        self.assertEqual(found[1]['note'], 'no uncompiled model'); self.assertEqual(len(found), 2)
        step = LINTEL.replace('lintel', 'step').replace('2.8', '0.2')
        self.assertEqual(openings.doorways(SET, {'t': model(*JAMBS, LINTEL, step)})[0]['height'], 2.8)
        open_ = openings.doorways(SET, {'t': model(JAMBS[0])})[0]
        self.assertEqual((open_['width'], open_['height'], open_['left'], open_['right']), (None, None, None, 2.0))

    def test_black_faces_are_doors_or_windows(self):
        text = model(WALK, wall('door', 'black_01', 'x', -2, -4, -2, 0.1, 2.5), wall('window', 'black_01', 'y', -2, -4, -3, 3, 5), wall('beside', 'black_01', 'y', -2, -3, -2, 3, 5),
                     wall('brick', 'brick', 'x', -2, -4, -2, 0, 2), wall('speck', 'black_01', 'x', 3, 0, 0.1, 0, 2))
        rows = openings.black(text, ['BLACK*'])
        self.assertEqual([(row['axis'], row['plane'], row['along'], row['kind']) for row in rows],
                         [('x', -2.0, [-4.0, -2.0], 'door'), ('y', -2.0, [-4.0, -3.0], 'window'), ('y', -2.0, [-3.0, -2.0], 'window')])
        self.assertEqual(rows[0]['ground'], 0.0)
        self.assertEqual(openings.black(model(wall('door', 'black', 'x', -2, -4, -2, 0.1, 2.5)), ['black'])[0]['ground'], None)


if __name__ == '__main__':
    unittest.main()
