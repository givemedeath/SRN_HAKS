import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.envkit import toolset_paint

REPO = Path(__file__).resolve().parents[2]


def tile(number, model, ground, *, door=None):
    corners = ''.join(f'{corner}={ground}\n{corner}Height=0\n' for corner in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'))
    edges = ''.join(f'{edge}=\n' for edge in ('Top', 'Right', 'Bottom', 'Left'))
    text = f'[TILE{number}]\nModel={model}\n{corners}{edges}Doors={0 if door is None else 1}\n\n'
    return text + (f'[TILE{number}DOOR0]\nType={door}\nX=0\nY=0\nZ=0\nOrientation=0\n\n' if door is not None else '')


def group(number, name, held):
    return f'[GROUP{number}]\nName={name}\nRows=1\nColumns=1\nTile0={held}\n\n'


HEAD = ('[GENERAL]\nName=T\nDefault=Deck\nFloor=Deck\nBorder=Deck\n\n[TERRAIN TYPES]\nCount=1\n\n[TERRAIN0]\nName=Deck\n\n'
        '[CROSSER TYPES]\nCount=0\n\n[PRIMARY RULES]\nCount=0\n\n[TILES]\nCount=4\n\n')
SET = (HEAD + tile(0, 'a_tower', 'Deck') + tile(1, 'A_hall', 'Deck', door=268) + tile(2, 'a_plain', 'Deck') + tile(3, 'a_hut', 'Deck', door=0)
       + '[GROUPS]\nCount=3\n\n' + group(0, 'Tower', 0) + group(1, 'Hall', 1) + group(2, 'Hut', 3))
PALETTE = {'a_tower': 'X: Tower', 'a_hall': 'X: Hall', 'a_hut': 'X: Hut'}


class Paint(unittest.TestCase):
    def test_a_fill_is_no_group_s_own_tile(self):
        # the dark deck was first filled with a tower's tile, which the Toolset paints nothing over (2026-11-24)
        planned = toolset_paint.plan(SET, PALETTE)
        self.assertEqual(planned['grounds'], [['Deck', 2]])
        self.assertEqual([(one['name'], one['tiles'], one['doors']) for one in planned['groups']], [('X: Tower', [0], []), ('X: Hall', [1], [268]), ('X: Hut', [3], [])])
        self.assertEqual(toolset_paint.area_name(planned, 'Deck'), 'ekt00')
        self.assertEqual([one['number'] for one in toolset_paint.plan(SET, PALETTE, {1})['groups']], [1])

    def test_a_group_the_palette_lacks_or_names_twice_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'does not list'):
            toolset_paint.plan(SET, {'a_hall': 'X: Hall'})
        with self.assertRaisesRegex(ValueError, 'twice'):
            toolset_paint.plan(SET, {**PALETTE, 'a_hut': 'X: Hall'})

    def test_a_number_the_set_has_no_group_of_is_refused(self):
        # an empty plan built the plain areas of other tilesets (review of PR 199)
        for only in ({9}, {1, 9}, set()):
            with self.assertRaisesRegex(ValueError, 'no group'):
                toolset_paint.plan(SET, PALETTE, only)

    def test_run_keeps_whole_groups_only_and_stops_at_a_paint_left(self):
        planned = toolset_paint.plan(SET, PALETTE)
        hall = planned['groups'][1]
        with tempfile.TemporaryDirectory() as temporary:
            module = Path(temporary) / 'saved.mod'
            module.write_bytes(b'module')
            for laid, doors, kept in (([2, 2], [], False), ([2, 1], [268], True)):
                wrong = toolset_paint.judge(planned, hall, laid, doors)
                with mock.patch.object(toolset_paint, 'judged', return_value=wrong):
                    toolset_paint.keep(planned, hall, module, temporary)
                self.assertEqual((Path(temporary) / '1.mod').is_file(), kept)
            wrong = toolset_paint.judge(planned, hall, [1, 0], [268])
            with mock.patch.object(toolset_paint, 'judged', return_value=wrong), self.assertRaisesRegex(ValueError, 'not undone'):
                toolset_paint.keep(planned, hall, module, temporary)

    def test_judge_holds_a_saved_area_to_its_group(self):
        planned = toolset_paint.plan(SET, PALETTE)
        tower, hall, hut = planned['groups']
        self.assertEqual(toolset_paint.judge(planned, hall, [2, 1, 2], [268]), [])
        self.assertEqual(toolset_paint.judge(planned, hut, [3, 2], []), [])  # a generic hook makes no door
        self.assertEqual(toolset_paint.judge(planned, hall, [2, 2], []), ['tiles missing: 1', 'doors [], not [268]'])
        self.assertEqual(toolset_paint.judge(planned, tower, [0, 1], []), ['tiles of another group: 1'])  # an undo that did not

    def test_every_group_of_the_unified_set_has_a_ground(self):
        from tools.tilekit import inventory
        text = (REPO / 'srn_t_srx01' / 'srx01.set').read_bytes().decode('cp1252')
        read = inventory.read_set(text)
        planned = toolset_paint.plan(text, {one['model'].lower(): one['model'] for one in read['tiles']})
        self.assertEqual(len(planned['groups']), 213)
        own = {number for held in read['groups'] for number in held['tiles']}
        self.assertFalse(own & {fill for _, fill in planned['grounds']})


if __name__ == '__main__':
    unittest.main()
