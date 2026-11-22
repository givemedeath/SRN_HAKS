"""The merged city tileset (srn_t_srx01) is what `tilekit merge` makes of its three source sets today: nothing was
lost, renamed by hand or left behind by a source set that changed since."""
import json
import re
import unittest
from pathlib import Path

from tools.tilekit import inventory, merge

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_srx01', 'srn_t_dgt04', 'srn_t_udp1', 'srn_t_fcx01', 'srn_t_common', 'srn_2da')  # what this reads: named so the test selector runs it when one changes
SPEC_PATH = REPO / 'docs' / 'tilesets' / 'srx01' / 'merge.json'
SPEC = json.loads(SPEC_PATH.read_text(encoding='utf-8'))
NAMES = json.loads((REPO / SPEC['names']).read_text(encoding='utf-8'))
INPUTS, OUTPUTS = merge.paths(REPO, SPEC)
ORDER = [family['set'] for family in SPEC['families']]


def keyed(text):
    """{section name: {key: value}} of a set file."""
    return dict(inventory.sections(text))


class Rules(unittest.TestCase):
    BESIDE = merge.reach([['A', 'A', 'G', 'G'], ['G', 'M', 'G', 'G'], ['C', 'C', 'T', 'C'], ['P', 'H', 'P', 'P']], [('C', 'A'), ('C', 'P')])

    def test_the_way_to_a_terrain_starts_with_a_neighbour(self):
        self.assertEqual(merge.toward(self.BESIDE, 'M', 'T'), 'G')  # mall, grass, asphalt, concrete, tenement
        self.assertEqual(merge.toward(self.BESIDE, 'T', 'M'), 'C')
        self.assertEqual(merge.toward(self.BESIDE, 'H', 'M'), 'P')
        self.assertIsNone(merge.toward(self.BESIDE, 'C', 'A'))  # a join lays them side by side
        self.assertIsNone(merge.toward(self.BESIDE, 'M', 'nowhere'))

    def test_only_pairs_of_two_families_that_cannot_touch_get_a_rule(self):
        family = {'A': 'sub', 'G': 'sub', 'M': 'sub', 'C': 'city', 'T': 'city', 'P': 'arc', 'H': 'arc'}
        own = [merge._rule('M', 'A', 'G'), merge._rule('m', 'a', 'A')]  # the second says the first again in another case
        made = merge.rules(own, family, self.BESIDE, raised=('C',), joins=[('C', 'A'), ('C', 'P')])
        said = {(rule['Placed'], rule['PlacedHeight'], rule['Adjacent'], rule['AdjacentHeight']): rule['Changed'] for rule in made}
        self.assertEqual(len(said), len(made)); self.assertEqual(made[0], own[0])
        self.assertNotIn(('C', '0', 'A', '0'), said); self.assertNotIn(('G', '0', 'M', '0'), said)  # neighbours; and one family
        self.assertEqual(said[('M', '0', 'T', '0')], 'G'); self.assertEqual(said[('T', '0', 'H', '0')], 'C')
        self.assertEqual((said[('C', '1', 'A', '0')], said[('A', '0', 'C', '1')], said[('P', '0', 'C', '1')]), ('C', 'C', 'C'))
        self.assertEqual(made, merge.rules(own, family, self.BESIDE, raised=('C',), joins=[('C', 'A'), ('C', 'P')]))

    def test_a_names_file_that_says_a_name_twice_or_too_long_is_refused(self):
        one = {'set': 'a', 'name': 'Old', 'key': 'New', 'display': 'New'}
        with self.assertRaisesRegex(ValueError, 'named twice'):
            merge.maps({'terrains': [one, {**one, 'key': 'Other'}], 'crossers': []})
        with self.assertRaisesRegex(ValueError, 'share a key'):
            merge.maps({'terrains': [one], 'crossers': [{**one, 'key': 'new'}]})
        with self.assertRaisesRegex(ValueError, 'longer than'):
            merge.maps({'terrains': [{**one, 'key': 'A' * 17}], 'crossers': []})
        with self.assertRaisesRegex(ValueError, 'folds into no terrain'):
            merge.maps({'terrains': [one], 'crossers': [], 'folds': [{'set': 'a', 'name': 'x', 'into': 'Gone'}]})
        self.assertEqual(merge.maps({'terrains': [one], 'crossers': [], 'folds': [{'set': 'a', 'name': 'Odl', 'into': 'New'}, {'set': 'a', 'name': 'Unused', 'into': None}]})[0],
                         {'a': {'old': 'New', 'odl': 'New'}})

    def test_an_edge_row_keeps_its_open_and_raised_corners(self):
        names = {'terrains': [{'set': 'a', 'name': 'Old', 'key': 'New'}, {'set': 'a', 'name': 'Deck', 'key': 'Bridge'}], 'crossers': [{'set': 'a', 'name': 'Rd', 'key': 'Road'}],
                 'edgeNames': [{'set': 'a', 'name': 'Raod', 'into': 'Road'}]}
        table = '2DA V2.0\r\n\r\n  Corner1 Edge Corner2 Height Model\r\n0 Old **** **** 0 m0\r\n\r\n1 old+ rd Old 1 m1\r\n2 Old Deck Old 0 m2\r\n3 Old Raod Old 0 m3\r\n'
        rows = [line.split() for line in merge.merged_edge({'a': table}, names, {'families': [{'set': 'a'}]}).split('\r\n')[3:] if line]
        self.assertEqual(rows, [['0', 'New', '****', '****', '0', 'm0'], ['1', 'New+', 'Road', 'New', '1', 'm1'], ['2', 'New', 'Bridge', 'New', '0', 'm2'],
                                ['3', 'New', 'Road', 'New', '0', 'm3']])
        with self.assertRaisesRegex(ValueError, 'no name'):
            merge.merged_edge({'a': table.replace('0 Old ', '0 Other ')}, names, {'families': [{'set': 'a'}]})


def small(model='m1'):
    """A set file of two tiles and one group, as a source set."""
    lines = ['[GENERAL]', 'Name=A', 'Border=Old', 'Default=Old', 'Floor=Old', '', '[TERRAIN TYPES]', 'Count=1', '', '[TERRAIN0]', 'Name=Old', '', '[CROSSER TYPES]', 'Count=0', '',
             '[PRIMARY RULES]', 'Count=0', '', '[TILES]', 'Count=2', '']
    for number, name in enumerate(('m0', model)):
        lines += [f'[TILE{number}]', f'Model={name}', 'TopLeft=Old', 'TopRight=old', 'BottomLeft=Old', 'BottomRight=Old', 'Top=', 'Right=', 'Bottom=', 'Left=', 'Doors=0', '']
    return '\r\n'.join(lines + ['[GROUPS]', 'Count=1', '', '[GROUP0]', 'Name=Hut', 'Rows=1', 'Columns=1', 'Tile0=1', '']).encode()


class Refresh(unittest.TestCase):
    def test_a_new_group_of_a_source_set_is_named_and_the_merged_set_made_again(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder); (repo / 'srn_t_a').mkdir(); (repo / 'srn_2da').mkdir(); home = repo / 'docs' / 'tilesets' / 'm'; home.mkdir(parents=True)
            (repo / 'srn_t_a' / 'a.set').write_bytes(small())
            (repo / 'srn_2da' / 'a_edge.2da').write_bytes('\r\n'.join(['2DA V2.0', '', '  Corner1 Edge Corner2 Height Model', '0 Old **** Old 0 e0', '']).encode())
            names = {'categories': ['Streets', 'Unsorted'], 'terrains': [{'set': 'a', 'name': 'Old', 'key': 'New', 'display': 'Streets: New'}], 'crossers': [], 'groups': []}
            (home / 'names.json').write_text(json.dumps(names), encoding='utf-8')
            spec = {'set': 'm', 'display': 'M', 'names': 'docs/tilesets/m/names.json', 'families': [{'set': 'a', 'label': 'City'}], 'general': 'a', 'grass': 'a'}
            (home / 'merge.json').write_text(json.dumps(spec), encoding='utf-8')
            gff = lambda arguments: Path(arguments[3]).write_bytes(Path(arguments[1]).read_bytes())
            self.assertEqual(merge.refresh(repo, {'other': ('Hut', 'A Hut')}, gff=gff), {})  # no merged set holds that source set
            told = merge.refresh(repo, {'a': ('Hut', 'A Hut')}, gff=gff)
            self.assertEqual(told['m']['tiles'], 2)
            self.assertEqual(json.loads((home / 'names.json').read_text(encoding='utf-8'))['groups'][0]['display'], 'Unsorted: A Hut')
            made = (repo / 'srn_t_m' / 'm.set').read_bytes().decode()
            self.assertIn('TopRight=New\r\n', made); self.assertIn('Name=M\r\n', made); self.assertIn('Tile0=1\r\n', made)
            self.assertEqual(merge.stale(repo, spec, home / 'merge.json', home / 'merged.json'), [])
            (repo / 'srn_t_a' / 'a.set').write_bytes(small('m9'))
            self.assertEqual(merge.stale(repo, spec, home / 'merge.json', home / 'merged.json'), ['set:a'])
            with self.assertRaisesRegex(ValueError, 'no category'):
                merge.refresh(repo, {'a': ('Other', 'Other')}, district='Nowhere', gff=gff)


class Merged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.made = merge.work(REPO, SPEC); cls.text = OUTPUTS['set'].read_bytes().decode('cp1252')
        cls.merged = keyed(cls.text); cls.laid = inventory.read_set(cls.text)
        cls.sources = {name: INPUTS[f'set:{name}'].read_bytes().decode('cp1252') for name in ORDER}
        cls.terrains, cls.crossers = merge.maps(NAMES)

    def test_the_pack_holds_what_a_merge_of_todays_sources_writes(self):
        self.assertEqual(merge.stale(REPO, SPEC, SPEC_PATH, SPEC_PATH.with_name('merged.json')), [])  # a source set, the names or the spec changed: merge again
        self.assertEqual(self.text, self.made['set'])
        self.assertEqual(OUTPUTS['edge'].read_bytes().decode('cp1252'), self.made['edge'])
        self.assertEqual(self.made['set'], merge.work(REPO, SPEC)['set'])  # the same bytes each time

    def test_no_two_groups_begin_with_one_model(self):
        models = [group['model'].lower() for group in self.made['groups']]  # the Toolset would lay the first for both
        self.assertEqual(len(models), len(set(models)))
        self.assertEqual([group['display'] for group in self.made['groups'] if group['display'].endswith(')')], [])  # no copy is left to tell apart

    def test_every_source_tile_is_there_once_and_only_its_names_changed(self):
        count = 0
        for name in ORDER:
            source = keyed(self.sources[name]); first = self.made['first'][name]; self.assertEqual(first, count)
            for section, keys in source.items():
                found = re.fullmatch(r'TILE(\d+)(DOOR\d+)?', section)
                if not found:
                    continue
                count += 0 if found.group(2) else 1
                now = self.merged[f'TILE{first + int(found.group(1))}{found.group(2) or ""}']; want = dict(keys)
                if not found.group(2):
                    for key in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'):
                        want[key] = self.terrains[name][keys[key].lower()]
                    for key in ('Top', 'Right', 'Bottom', 'Left'):
                        want[key] = self.crossers[name][keys[key].lower()] if keys.get(key) else keys.get(key, '')
                self.assertEqual(now, want, f'{name} {section}')
        self.assertEqual(count, len(self.laid['tiles'])); self.assertEqual(int(self.merged['TILES']['Count']), count)
        self.assertEqual(len([section for section in self.merged if re.fullmatch(r'TILE\d+', section)]), count)

    def test_every_name_a_tile_or_rule_uses_is_declared(self):
        terrains = {name.lower() for name in self.laid['terrains']}; crossers = {name.lower() for name in self.laid['crossers']}
        self.assertEqual(self.laid['terrains'], [entry['key'] for entry in NAMES['terrains']]); self.assertEqual(self.laid['crossers'], [entry['key'] for entry in NAMES['crossers']])
        self.assertEqual({corner.lower() for tile in self.laid['tiles'] for corner in tile['corners']} - terrains, set())
        self.assertEqual({crosser.lower() for tile in self.laid['tiles'] for crosser in tile['crossers'] if crosser} - crossers, set())
        rules = [keys for section, keys in self.merged.items() if re.fullmatch(r'PRIMARY RULE\d+', section)]
        self.assertEqual(len(rules), int(self.merged['PRIMARY RULES']['Count']))
        self.assertEqual({rule[key].lower() for rule in rules for key in ('Placed', 'Adjacent', 'Changed')} - terrains, set())
        self.assertEqual({self.merged['GENERAL'][key].lower() for key in ('Border', 'Default', 'Floor')} - terrains, set())
        self.assertIn('GRASS', self.merged)

    def test_two_families_terrains_touch_or_have_a_rule_that_leads_there(self):
        family = {entry['key']: entry['set'] for entry in NAMES['terrains']}
        beside = merge.reach([tile['corners'] for tile in self.laid['tiles']], [tuple(pair) for pair in SPEC['joins']])
        said = {(keys['Placed'], keys['Adjacent']): keys['Changed'] for section, keys in self.merged.items()
                if re.fullmatch(r'PRIMARY RULE\d+', section) and keys['PlacedHeight'] == keys['AdjacentHeight'] == '0'}
        lacking = [(one, other) for one in family for other in family if family[one] != family[other] and other not in beside.get(one, ()) and (one, other) not in said
                   and one in beside and other in beside]  # a terrain no tile has (off the palette) is no one's neighbour
        self.assertEqual(lacking, [])
        self.assertEqual([(pair, changed) for pair, changed in said.items() if family[pair[0]] != family[pair[1]] and changed not in beside[pair[0]]], [])

    def test_every_group_holds_its_source_tiles_under_one_name(self):
        groups = [keys for section, keys in self.merged.items() if re.fullmatch(r'GROUP\d+', section)]; index = 0
        self.assertEqual(len(groups), int(self.merged['GROUPS']['Count'])); self.assertEqual(len({group['Name'].lower() for group in groups}), len(groups))
        models = {tile['number']: tile['model'] for tile in self.laid['tiles']}; begun = set()
        for name in ORDER:
            theirs = inventory.read_set(self.sources[name]); source = {tile['number']: tile['model'] for tile in theirs['tiles']}
            for section, keys in keyed(self.sources[name]).items():
                if not re.fullmatch(r'GROUP\d+', section):
                    continue
                size = int(keys['Rows']) * int(keys['Columns'])
                if source[int(keys['Tile0'])].lower() in begun:  # a later family's copy of a building: left out, the Toolset would lay the first
                    continue
                begun.add(source[int(keys['Tile0'])].lower()); now = groups[index]; index += 1
                self.assertEqual((now['Rows'], now['Columns']), (keys['Rows'], keys['Columns']))
                self.assertEqual([models[int(now[f'Tile{at}'])] for at in range(size)], [source[int(keys[f'Tile{at}'])] for at in range(size)], f'{name} {keys["Name"]}')
        self.assertEqual(index, len(groups))
        listed = [entry['RESREF']['value'] for node in self.made['palette']['MAIN']['value'][:2] for entry in node['LIST']['value']]
        self.assertEqual(len(listed), len(groups))

    def test_every_model_the_set_and_its_edge_table_name_is_in_a_pack_it_loads_with(self):
        held = {path.stem.lower() for pack in PACKS for path in (REPO / pack).glob('*.mdl')}
        edge = set(inventory.edge_models(OUTPUTS['edge'].read_bytes().decode('cp1252'))[0])
        absent = sorted(({tile['model'] for tile in self.laid['tiles']} | edge) - held)
        self.assertEqual(absent, sorted(SPEC['absent']))  # the edge models a source set already lacked, each written down


if __name__ == '__main__':
    unittest.main()
