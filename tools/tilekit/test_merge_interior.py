"""The merged interior tileset (srn_t_srx02) is what `tilekit merge` makes of its four source sets today, and what the
merge learned for it: a group left off the palette, a set that names several groups alike, a set with no edge table."""
import json
import re
import unittest
from pathlib import Path

from tools.tilekit import inventory, merge

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_srx02', 'srn_t_udp2', 'srn_t_tfb01', 'srn_t_tbx78', 'srn_t_nac01', 'srn_t_common', 'srn_2da')  # what this reads: named so the test selector runs it when one changes
SPEC_PATH = REPO / 'docs' / 'tilesets' / 'srx02' / 'merge.json'
SPEC = json.loads(SPEC_PATH.read_text(encoding='utf-8'))
NAMES = json.loads((REPO / SPEC['names']).read_text(encoding='utf-8'))
INPUTS, OUTPUTS = merge.paths(REPO, SPEC)
ORDER = [family['set'] for family in SPEC['families']]
DOORS = {str(old): new for old, new in SPEC['doors'].items()}
SMALL = ('[GENERAL]\r\nName=a\r\nBorder=Wall\r\nDefault=Wall\r\nFloor=Wall\r\n\r\n[TILES]\r\nCount=3\r\n\r\n'
         + ''.join(f'[TILE{at}]\r\nModel=m{at}\r\nTopLeft=Wall\r\nTopRight=Wall\r\nBottomLeft=Wall\r\nBottomRight=Wall\r\nTop=\r\nRight=\r\nBottom=\r\nLeft=\r\n\r\n' for at in range(3))
         + '[GROUPS]\r\nCount=3\r\n\r\n' + ''.join(f'[GROUP{at}]\r\nName={name}\r\nRows=1\r\nColumns=1\r\nTile0={at}\r\n\r\n' for at, name in enumerate(('room', 'room', 'den'))))


class Learned(unittest.TestCase):
    names = {'terrains': [{'set': 'a', 'name': 'Wall', 'key': 'Wall', 'display': 'Wall'}], 'crossers': [],
             'groups': [{'set': 'a', 'name': 'room', 'display': 'Room A', 'repeats': ['Room A', 'Room B']}, {'set': 'a', 'name': 'den', 'display': 'Den', 'palette': False}]}
    spec = {'set': 'm', 'display': 'M', 'families': [{'set': 'a', 'label': 'Home', 'edge': False}], 'general': 'a', 'grass': 'a'}

    def test_groups_named_alike_each_get_a_name_and_a_display(self):
        text, _, groups = merge.merged_set({'a': SMALL}, self.names, self.spec)
        self.assertEqual([(group['name'], group['display']) for group in groups], [('room', 'Room A'), ('room_2', 'Room B'), ('den', 'Den')])
        self.assertIn('Name=room_2\r\n', text)
        with self.assertRaisesRegex(ValueError, 'more often than its names entry lists'):
            merge.merged_set({'a': SMALL.replace('Name=den', 'Name=room')}, self.names, self.spec)

    def test_a_group_off_the_palette_stays_in_the_set(self):
        text, _, groups = merge.merged_set({'a': SMALL}, self.names, self.spec)
        self.assertIn('Name=den\r\n', text)
        shown = [entry['NAME']['value'] for node in merge.palette(self.names, groups)['MAIN']['value'][:2] for entry in node['LIST']['value']]
        self.assertEqual(shown, ['Room A', 'Room B'])

    def test_a_set_with_no_edge_table_is_asked_for_none(self):
        inputs, _ = merge.paths(REPO, {**self.spec, 'names': 'names.json'})
        self.assertEqual(sorted(inputs), ['names', 'set:a'])
        self.assertEqual(merge.merged_edge({}, self.names, self.spec).splitlines()[3:], [])


class Merged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.made = merge.work(REPO, SPEC); cls.text = OUTPUTS['set'].read_bytes().decode('cp1252')
        cls.merged = dict(inventory.sections(cls.text)); cls.laid = inventory.read_set(cls.text)
        cls.sources = {name: INPUTS[f'set:{name}'].read_bytes().decode('cp1252') for name in ORDER}

    def test_the_pack_holds_what_a_merge_of_todays_sources_writes(self):
        self.assertEqual(merge.stale(REPO, SPEC, SPEC_PATH, SPEC_PATH.with_name('merged.json')), [])  # a source set, the names or the spec changed: merge again
        self.assertEqual(self.text, self.made['set'])
        self.assertEqual(OUTPUTS['edge'].read_bytes().decode('cp1252'), self.made['edge'])
        self.assertNotIn(b'\r', OUTPUTS['edge'].read_bytes())

    def test_the_numbers_of_the_first_merge_never_change(self):
        record = json.loads((REPO / SPEC['numbers']).read_text(encoding='utf-8'))['tiles']
        self.assertEqual(record[:4], [['udp2', 0, 229], ['tfb01', 0, 338], ['tbx78', 0, 84], ['nac01', 0, 17]])
        self.assertEqual(int(self.merged['TILES']['Count']), len(self.laid['tiles']))
        models = [tile['model'] for name in ORDER for tile in inventory.read_set(self.sources[name])['tiles']]
        self.assertEqual([tile['model'] for tile in self.laid['tiles']][:668], models[:668])

    def test_it_is_an_interior_on_one_wall(self):
        general = self.merged['GENERAL']
        self.assertEqual((general['Name'], general['Interior'], general['Border'], general['Default']), ('SRX02', '1', 'Wall', 'Wall'))
        self.assertEqual(self.laid['terrains'], [entry['key'] for entry in NAMES['terrains']]); self.assertEqual(self.laid['crossers'], [entry['key'] for entry in NAMES['crossers']])
        self.assertEqual({corner for tile in self.laid['tiles'] for corner in tile['corners']} - set(self.laid['terrains']), set())
        self.assertEqual({crosser for tile in self.laid['tiles'] for crosser in tile['crossers'] if crosser} - set(self.laid['crossers']), set())
        for tile in self.laid['tiles']:  # every floor meets only the wall: two families join through it with no tile of their own
            self.assertLessEqual(len(set(tile['corners']) - {'Wall'}), 1, tile['model'])

    def test_two_families_floors_have_a_rule_that_leads_through_the_wall(self):
        family = {entry['key']: entry['set'] for entry in NAMES['terrains']}
        said = {(keys['Placed'], keys['Adjacent']): keys['Changed'] for section, keys in self.merged.items() if re.fullmatch(r'PRIMARY RULE\d+', section)}
        self.assertEqual(len(said), int(self.merged['PRIMARY RULES']['Count']))
        for one in family:
            for other in family:
                if family[one] != family[other] and 'Wall' not in (one, other):
                    self.assertEqual(said.get((one, other)), 'Wall', (one, other))

    def test_every_door_hook_names_a_type_the_toolset_knows_in_this_set(self):
        rows = {cells[0]: cells for cells in (inventory.words(line) for line in (REPO / 'srn_2da' / 'doortypes.2da').read_text(encoding='cp1252').splitlines()[3:]) if cells}
        for old, new in DOORS.items():
            self.assertEqual(rows[str(new)][3], 'SRX02'); self.assertEqual(rows[str(new)][2:3] + rows[str(new)][4:], rows[old][2:3] + rows[old][4:])
        used = {keys['Type'] for section, keys in self.merged.items() if re.fullmatch(r'TILE\d+DOOR\d+', section)}
        self.assertEqual(sorted(kind for kind in used if rows[kind][3] not in ('****', 'SRX02')), [])
        for section, keys in self.merged.items():  # nac01 wrote one hook X==-4.75, which no reader takes for a number
            if re.fullmatch(r'TILE\d+DOOR\d+', section):
                self.assertTrue(all(re.fullmatch(r'-?[0-9.]+', keys[axis]) for axis in 'XYZ'), section)

    def test_groups_begin_with_models_of_their_own_and_the_fantasy_ones_are_off_the_palette(self):
        models = [group['model'].lower() for group in self.made['groups']]; self.assertEqual(len(models), len(set(models)))
        self.assertEqual(len({group['name'].lower() for group in self.made['groups']}), len(models))
        self.assertEqual(int(self.merged['GROUPS']['Count']), len(models))
        listed = [entry['NAME']['value'] for node in self.made['palette']['MAIN']['value'][:2] for entry in node['LIST']['value']]
        hidden = sorted(entry['display'] for entry in NAMES['groups'] if not entry.get('palette', True))
        self.assertEqual(len(hidden), 9); self.assertEqual(set(listed) & set(hidden), set())
        self.assertEqual(len(listed), len(models) - len(hidden))
        self.assertEqual([name for name in ('Facility: Room 2x1 A', 'Facility: Room 1x2 B', 'Facility: Room 1x2 C') if name not in listed], [])

    def test_every_model_the_set_and_its_edge_table_name_is_in_a_pack_it_loads_with(self):
        held = {path.stem.lower() for pack in PACKS for path in (REPO / pack).glob('*.mdl')}
        edge = {model.lower() for model in inventory.edge_models(OUTPUTS['edge'].read_bytes().decode('cp1252'))[0]}
        self.assertEqual(sorted(({tile['model'].lower() for tile in self.laid['tiles']} | edge) - held), sorted(SPEC['absent']))  # each written down, with why


if __name__ == '__main__':
    unittest.main()
