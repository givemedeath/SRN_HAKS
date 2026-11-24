"""The merged city tileset (srn_t_srx01) is what `tilekit merge` makes of its three source sets today: nothing was
lost, renamed by hand or left behind by a source set that changed since."""
import json
import re
import unittest
from pathlib import Path

from tools.tilekit import joins, inventory, merge

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

DOORS = {str(old): new for old, new in SPEC.get('doors', {}).items()}


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
        rows = [line.split() for line in merge.merged_edge({'a': table}, names, {'families': [{'set': 'a'}]}).split('\n')[3:] if line]  # plain line ends, as git keeps a 2DA: CI checks out what a merge wrote
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
            # A building only a later family has is no copy; it becomes one when an earlier family gains the building.
            families = [{'set': 'z', 'label': 'Old Town'}, {'set': 'a', 'label': 'City'}, {'set': 'b', 'label': 'Town'}]
            (home / 'merge.json').write_text(json.dumps({**spec, 'families': families}), encoding='utf-8')
            shown = lambda added: {(entry['set'], entry['name']): entry['display'] for entry in merge.named(repo, added)[0][3]['groups']}
            self.assertEqual(shown({'b': ('Bar', 'A Bar')})[('b', 'Bar')], 'Unsorted: A Bar')
            self.assertEqual(shown({'b': ('Hut', 'A Hut')})[('b', 'Hut')], 'Unsorted: A Hut (town)')  # a has its Hut already
            both = shown({'b': ('Bar', 'A Bar'), 'z': ('Bar', 'A Bar')}); self.assertEqual((both[('z', 'Bar')], both[('b', 'Bar')]), ('Unsorted: A Bar', 'Unsorted: A Bar (town)'))
            first = shown({'z': ('Hut', 'A Hut')}); self.assertEqual((first[('z', 'Hut')], first[('a', 'Hut')]), ('Unsorted: A Hut', 'Unsorted: A Hut (city)'))
            (home / 'merge.json').write_text(json.dumps(spec), encoding='utf-8')
            before = (home / 'names.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'no category'):  # what an install asks before it changes a source set: nothing is written
                merge.named(repo, {'a': ('Other', 'Other')}, district='Nowhere')
            self.assertEqual(len(merge.named(repo, {'a': ('Other', 'Other')})), 1); self.assertEqual((home / 'names.json').read_bytes(), before)

    def test_a_tile_keeps_its_number_when_a_family_before_it_grows(self):
        number, record = merge.numbered({'a': 2, 'b': 2}, ['j1'])
        self.assertEqual(record, [['a', 0, 2], ['b', 0, 2], ['join', 'j1']]); self.assertEqual(number[('b', 0)], 2); self.assertEqual(number[('join', 'j1')], 4)
        grown, again = merge.numbered({'a': 4, 'b': 3}, ['j1', 'j2'], record)  # an envkit building in a, a tile in b, a new join
        self.assertEqual({key: grown[key] for key in number}, number)  # every number given before is kept
        self.assertEqual(again, [['a', 0, 2], ['b', 0, 2], ['join', 'j1'], ['a', 2, 2], ['b', 2, 1], ['join', 'j2']])
        self.assertEqual((grown[('a', 2)], grown[('a', 3)], grown[('b', 2)], grown[('join', 'j2')]), (5, 6, 7, 8))
        self.assertEqual(merge.numbered({'a': 4, 'b': 3}, ['j1', 'j2'], again), (grown, again))  # a merge again writes the same record
        self.assertEqual(record, [['a', 0, 2], ['b', 0, 2], ['join', 'j1']])  # the record given is not changed
        with self.assertRaisesRegex(ValueError, 'tiles 0 to 1 of b, which the set no longer has'):
            merge.numbered({'a': 4, 'b': 1}, ['j1'], record)
        with self.assertRaisesRegex(ValueError, 'join tile j1, which is no longer built'):
            merge.numbered({'a': 2, 'b': 2}, [], record)
        with self.assertRaisesRegex(ValueError, 'names a tile twice'):
            merge.numbered({'a': 2}, [], [['a', 0, 2], ['a', 1, 1]])
        for run in (['a', 0], ['join', 'j1', 1], ['a', 0, '2'], ['a', -1, 2]):
            with self.assertRaisesRegex(ValueError, 'a run that is neither'):
                merge.numbered({'a': 2}, ['j1'], [run])

    def test_a_lost_numbers_record_is_refused_once_tiles_would_move(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder); (repo / 'srn_2da').mkdir(); home = repo / 'docs' / 'tilesets' / 'm'; home.mkdir(parents=True)
            for name in 'ab':
                (repo / f'srn_t_{name}').mkdir(); (repo / f'srn_t_{name}' / f'{name}.set').write_bytes(small().replace(b'Model=m', b'Model=' + name.encode()))
                (repo / 'srn_2da' / f'{name}_edge.2da').write_bytes(b'2DA V2.0\n\n  Corner1 Edge Corner2 Height Model\n')
            names = {'categories': ['Unsorted'], 'terrains': [{'set': name, 'name': 'Old', 'key': key, 'display': key} for name, key in (('a', 'New'), ('b', 'Newer'))],
                     'crossers': [], 'groups': [{'set': name, 'name': 'Hut', 'display': 'Hut ' + name} for name in 'ab']}
            (home / 'names.json').write_text(json.dumps(names), encoding='utf-8')
            spec = {'set': 'm', 'display': 'M', 'names': 'docs/tilesets/m/names.json', 'numbers': 'docs/tilesets/m/numbers.json',
                    'families': [{'set': 'a', 'label': 'City'}, {'set': 'b', 'label': 'Town'}], 'general': 'a', 'grass': 'a'}
            (home / 'merge.json').write_text(json.dumps(spec), encoding='utf-8')
            gff = lambda arguments: Path(arguments[3]).write_bytes(Path(arguments[1]).read_bytes())
            merge.merge(repo, home / 'merge.json', home / 'merged.json', gff=gff)
            self.assertEqual(json.loads((home / 'numbers.json').read_text(encoding='utf-8'))['tiles'], [['a', 0, 2], ['b', 0, 2]])
            more = small().replace(b'Model=m', b'Model=a').decode().replace('Count=2', 'Count=3').replace(
                '[GROUPS]', '[TILE2]\r\nModel=a2\r\nTopLeft=Old\r\nTopRight=Old\r\nBottomLeft=Old\r\nBottomRight=Old\r\nTop=\r\nRight=\r\nBottom=\r\nLeft=\r\nDoors=0\r\n\r\n[GROUPS]')
            (repo / 'srn_t_a' / 'a.set').write_bytes(more.encode())
            merge.merge(repo, home / 'merge.json', home / 'merged.json', gff=gff)  # a's new tile takes the number after b's
            self.assertEqual(json.loads((home / 'numbers.json').read_text(encoding='utf-8'))['tiles'], [['a', 0, 2], ['b', 0, 2], ['a', 2, 1]])
            self.assertEqual(merge.stale(repo, spec, home / 'merge.json', home / 'merged.json'), [])
            kept = (home / 'numbers.json').read_bytes(); (home / 'numbers.json').unlink()
            self.assertEqual(merge.stale(repo, spec, home / 'merge.json', home / 'merged.json'), ['numbers'])
            with self.assertRaisesRegex(ValueError, 'numbers record numbers.json is missing, and without it tiles of m.set would take other numbers'):
                merge.merge(repo, home / 'merge.json', home / 'merged.json', gff=gff)
            (home / 'numbers.json').write_text('[]', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'is no numbers record'):
                merge.work(repo, spec)
            (home / 'numbers.json').write_bytes(kept); self.assertEqual(merge.stale(repo, spec, home / 'merge.json', home / 'merged.json'), [])
        names = {'terrains': [{'set': name, 'name': 'Old', 'key': key, 'display': key} for name, key in (('a', 'New'), ('b', 'Newer'))], 'crossers': [],
                 'groups': [{'set': name, 'name': 'Hut', 'display': 'Hut'} for name in 'ab']}
        spec = {'set': 'm', 'display': 'M', 'families': [{'set': 'a', 'label': 'City'}, {'set': 'b', 'label': 'Town'}], 'general': 'a', 'grass': 'a'}
        more = small().decode().replace('Count=2', 'Count=3').replace('[GROUPS]', '[TILE2]\r\nModel=m2\r\nTopLeft=Old\r\nTopRight=Old\r\nBottomLeft=Old\r\nBottomRight=Old\r\nTop=\r\nRight=\r\nBottom=\r\nLeft=\r\nDoors=0\r\n\r\n[GROUPS]')
        other = small().decode().replace('Model=m', 'Model=n')
        text, first, groups = merge.merged_set({'a': more, 'b': other}, names, spec, numbers=[['a', 0, 2], ['b', 0, 2]])
        self.assertEqual(first, {'a': 0, 'b': 2}); self.assertEqual(groups[1]['tiles'], [3])  # b's tiles where they were
        self.assertEqual(re.findall(r'\[TILE(\d+)\]\r\nModel=(\w+)', text), [('0', 'm0'), ('1', 'm1'), ('2', 'n0'), ('3', 'n1'), ('4', 'm2')])

    def test_the_numbers_record_of_the_set_is_what_the_set_holds(self):
        record = json.loads((REPO / SPEC['numbers']).read_text(encoding='utf-8'))['tiles']
        self.assertEqual(record[:3], [['dgt04', 0, 575], ['udp1', 0, 798], ['fcx01', 0, 239]])  # the numbers of release A: these runs never change
        self.assertEqual([run[1] for run in record[3:17]], [f'srx01_j{pair}{shape}_01' for pair in 'ap' for shape in '1234rst'])

    def test_a_group_s_empty_slot_stays_empty_and_its_model_is_its_first_tile_s(self):
        source = small().decode().replace('Rows=1\r\nColumns=1\r\nTile0=1', 'Rows=1\r\nColumns=3\r\nTile0=-1\r\nTile1=1\r\nTile2=0')
        names = {'terrains': [{'set': name, 'name': 'Old', 'key': key, 'display': key} for name, key in (('a', 'New'), ('b', 'Newer'))], 'crossers': [],
                 'groups': [{'set': name, 'name': 'Hut', 'display': 'Hut'} for name in 'ab']}
        spec = {'set': 'm', 'display': 'M', 'families': [{'set': 'a', 'label': 'City'}, {'set': 'b', 'label': 'Town'}], 'general': 'a', 'grass': 'a'}
        text, first, groups = merge.merged_set({'a': small().decode(), 'b': source.replace('Model=m', 'Model=n')}, names, spec)
        self.assertEqual(first, {'a': 0, 'b': 2}); self.assertEqual([(group['tiles'], group['model']) for group in groups], [([1], 'm1'), ([-1, 3, 2], 'n1')])
        self.assertIn('Tile0=-1\r\nTile1=3\r\nTile2=2\r\n', text)
        with self.assertRaisesRegex(ValueError, 'GENERAL has Floor=.Lost., which has no name'):
            merge.merged_set({'a': small().decode().replace('Floor=Old', 'Floor=Lost'), 'b': source}, names, {**spec, 'families': spec['families'][:1]})


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

    def test_every_door_hook_names_a_type_the_toolset_knows_in_this_set(self):
        """A door's types are listed by its area's tileset: a hook of a type keyed to a source set gave a door whose
        properties would not open (seen 2026-11-21). Envkit's type 58 is left as the source sets have it."""
        rows = {cells[0]: cells for cells in (inventory.words(line) for line in (REPO / 'srn_2da' / 'doortypes.2da').read_text(encoding='cp1252').splitlines()[3:]) if cells}
        for old, new in DOORS.items():
            self.assertEqual(rows[str(new)][3], SPEC['set'].upper()); self.assertEqual(rows[str(new)][2:3] + rows[str(new)][4:], rows[old][2:3] + rows[old][4:])
            self.assertIn(rows[old][3].lower(), ORDER)
        used = {keys['Type'] for section, keys in self.merged.items() if re.fullmatch(r'TILE\d+DOOR\d+', section)}
        self.assertEqual(sorted(kind for kind in used if rows[kind][3] not in ('****', SPEC['set'].upper()) and kind != '58'), [])

    def test_no_two_groups_begin_with_one_model(self):
        models = [group['model'].lower() for group in self.made['groups']]  # the Toolset would lay the first for both
        self.assertEqual(len(models), len(set(models)))
        self.assertEqual([group['display'] for group in self.made['groups'] if group['display'].endswith(')')], [])  # no copy is left to tell apart

    def test_every_source_tile_is_there_once_and_only_its_names_changed(self):
        # Where a tile stands is the numbers record's to say: a family's later tiles (an envkit building's) come after the joins.
        joined = joins.tiles(json.loads((REPO / SPEC['joinTiles']).read_text(encoding='utf-8')))
        number, _ = merge.numbered({name: len(inventory.read_set(self.sources[name])['tiles']) for name in ORDER}, [record['model'] for record in joined],
                                   json.loads((REPO / SPEC['numbers']).read_text(encoding='utf-8'))['tiles'])
        count = 0
        for name in ORDER:
            source = keyed(self.sources[name]); self.assertEqual(self.made['first'][name], number[(name, 0)])
            for section, keys in source.items():
                found = re.fullmatch(r'TILE(\d+)(DOOR\d+)?', section)
                if not found:
                    continue
                count += 0 if found.group(2) else 1
                now = self.merged[f'TILE{number[(name, int(found.group(1)))]}{found.group(2) or ""}']; want = dict(keys)
                if not found.group(2):
                    for key in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'):
                        want[key] = self.terrains[name][keys[key].lower()]
                    for key in ('Top', 'Right', 'Bottom', 'Left'):
                        want[key] = self.crossers[name][keys[key].lower()] if keys.get(key) else keys.get(key, '')
                if found.group(2) and want['Type'] in DOORS:  # a keyed door type is its copy keyed to this set
                    want['Type'] = str(DOORS[want['Type']])
                self.assertEqual(now, want, f'{name} {section}')
        for record in joined:
            self.assertEqual(self.laid['tiles'][number[('join', record['model'])]]['model'], record['model'])
        count += len(joined); self.assertEqual(sorted(number.values()), list(range(count)))  # every number once, none left out
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
                lead = source[next(int(keys[f'Tile{at}']) for at in range(size) if int(keys[f'Tile{at}']) >= 0)].lower()  # -1 is a slot with no tile
                if lead in begun:  # a later family's copy of a building: left out, the Toolset would lay the first
                    continue
                begun.add(lead); now = groups[index]; index += 1
                self.assertEqual((now['Rows'], now['Columns']), (keys['Rows'], keys['Columns']))
                self.assertEqual([models.get(int(now[f'Tile{at}'])) for at in range(size)], [source.get(int(keys[f'Tile{at}'])) for at in range(size)], f'{name} {keys["Name"]}')
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
