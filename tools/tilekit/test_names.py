"""The approved names of the unified city tileset (docs/tilesets/srx01/names.json) still cover what the three source
sets hold, and what was applied from them (placeable categories, door names) still agrees with them."""
import json
import re
import unittest
from pathlib import Path

from tools.tilekit import doorset, inventory

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_dgt04', 'srn_t_udp1', 'srn_t_fcx01', 'srn_tlk', 'srn_2da')  # what this reads: named so the test selector runs it when one changes
NAMES = json.loads((REPO / 'docs' / 'tilesets' / 'srx01' / 'names.json').read_text(encoding='utf-8'))
SETS = {name: inventory.read_set((REPO / f'srn_t_{name}' / f'{name}.set').read_bytes().decode('cp1252')) for name in ('dgt04', 'udp1', 'fcx01')}
TALK = {entry['id']: entry['text'] for entry in json.loads((REPO / 'srn_tlk' / 'srn.tlk.json').read_text(encoding='utf-8-sig'))['entries']}
CUSTOM = 16777216  # a reference to the custom talk table starts here
FIRST_CATEGORY, PARENT = 208, 144  # the first palette category of Shadowrun City, and its talk table row


class Names(unittest.TestCase):
    def test_the_talk_table_and_edge_table_have_the_line_ends_git_keeps(self):
        # Written with CR LF here, they are checked out with LF on CI, and every hash taken of them was wrong there
        # (the combat manifest's of the talk table, the merge lock's of the edge table: PR 191, 2026-11-23).
        for path in ('srn_tlk/srn.tlk.json', 'srn_tlk/allocations.json', 'srn_2da/srx01_edge.2da', 'srn_2da/doortypes.2da', 'srn_2da/genericdoors.2da'):
            self.assertNotIn(b'\r', (REPO / path).read_bytes(), path)

    def test_keys_are_unique_and_fit_the_set_file(self):
        keys = [entry['key'] for entry in NAMES['terrains'] + NAMES['crossers']]
        self.assertEqual(len(keys), len({key.lower() for key in keys}))  # the game reads names in any case
        self.assertEqual([key for key in keys if len(key) > 16 or not re.fullmatch(r'[A-Za-z0-9_]+', key)], [])
        shown = [entry['display'] for kind in ('terrains', 'crossers', 'groups') for entry in NAMES[kind]]
        self.assertEqual(sorted({name for name in shown if shown.count(name) > 1}), [])
        self.assertEqual({entry['category'] for kind in ('terrains', 'crossers', 'groups') for entry in NAMES[kind]} - set(NAMES['categories']), set())

    def test_every_source_name_maps_to_exactly_one_new_name(self):
        for kind, corners in (('terrains', 'corners'), ('crossers', 'crossers')):
            mapped = [(entry['set'], entry['name']) for entry in NAMES[kind]]
            self.assertEqual(len(mapped), len(set(mapped)))
            folded = {(fold['set'], fold['name']) for fold in NAMES['folds']} if kind == 'terrains' else set()
            self.assertEqual(set(mapped) & folded, set())
            for name, laid in SETS.items():
                with self.subTest(kind=kind, tileset=name):
                    used = {value for tile in laid['tiles'] for value in tile[corners] if value}
                    self.assertEqual(sorted((used | set(laid[kind])) - {old for one, old in set(mapped) | folded if one == name}), [])
        keys = {entry['key'] for entry in NAMES['terrains']}
        self.assertEqual([fold['name'] for fold in NAMES['folds'] if fold['into'] is not None and fold['into'] not in keys], [])

    def test_every_group_is_named_once(self):
        for name, laid in SETS.items():
            with self.subTest(tileset=name):
                self.assertEqual(sorted(group['name'] for group in laid['groups']), sorted(entry['name'] for entry in NAMES['groups'] if entry['set'] == name))

    def test_no_blueprint_is_lost_or_doubled_and_each_sits_in_its_category(self):
        placeables = NAMES['placeables']; categories = [category['name'] for category in placeables['categories']]
        resrefs = [blueprint['resref'] for blueprint in placeables['blueprints']]
        self.assertEqual(len(resrefs), len(set(resrefs)))
        self.assertEqual(sum(category['blueprints'] for category in placeables['categories']), len(resrefs))
        self.assertEqual(TALK[PARENT], placeables['parent'])
        self.assertEqual([TALK[PARENT + 1 + index] for index in range(len(categories))], categories)  # the palette names them by these rows
        wanted = {blueprint['resref']: FIRST_CATEGORY + categories.index(blueprint['to'].split(' > ')[1]) for blueprint in placeables['blueprints']}
        catalog = json.loads((REPO / 'docs' / 'additions' / 'catalog.json').read_text(encoding='utf-8-sig'))
        listed = {entry['blueprint']: entry['category'] for entry in catalog['placeables'] if entry.get('blueprint')}
        self.assertEqual({resref: listed.get(resref) for resref in wanted}, wanted)
        self.assertEqual(sorted(set(listed) - set(wanted)), [])  # a blueprint catalogued since the review is sorted here too

    def test_each_door_of_the_set_has_its_own_name(self):
        doors = NAMES['doors']['generic']
        self.assertEqual([(door['row'], door['label']) for door in doors], [(row, label) for row, label, *_ in doorset.rows()])
        self.assertEqual([TALK[reference - CUSTOM] for reference in doorset.NAMES.values()], [door['name'] for door in doors])
        table = (REPO / 'srn_2da' / 'genericdoors.2da').read_bytes().decode('cp1252')
        self.assertEqual(doorset.table(table), table)  # the table holds the rows the door set writes


if __name__ == '__main__':
    unittest.main()
