"""Compiled tile models and their ASCII sources: the pairs the manifest pins, the round trip, and the repository's own."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import test_impact
from tools.tilekit import compiled, inventory

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_common', 'srn_t_dgt04', 'srn_t_fcx01', 'srn_t_srx01', 'srn_t_udp1')  # the packs with sources: named so the test selector checks them out and runs this when one changes
BORROWED = ('srn_door', 'srn_placeable')  # the packs whose materials the sources may borrow (compiled.BORROW), named for the same reason

MODEL = '''newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
  parent NULL
endnode
node emitter Smoke
  parent t_a01
  birthrate 0
endnode
endmodelgeom t_a01
newanim animloop01 t_a01
  length 1.0
  transtime 0.25
  node dummy t_a01
    parent NULL
  endnode
  node emitter Smoke
    parent t_a01
    position 1.0 2.0 3.0
    birthratekey 2
      0.0 12.0
      1.0 12.0
    endlist
  endnode
doneanim animloop01 t_a01
donemodel t_a01
'''

BACK = '''newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
    parent NULL
endnode
node emitter smoke
    parent t_a01
endnode
endmodelgeom t_a01
newanim animloop01 t_a01
        length 1.0
        transtime 0.25
        node dummy t_a01
            parent NULL
        endnode
        node emitter smoke
            parent t_a01
            positionkey 1
                0.0 1.0 2.0 3.0
            birthratekey 2
                0.0 12.0
                1.0 12.0
        endnode
doneanim animloop01 t_a01
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


class RoundTripTests(unittest.TestCase):
    def test_a_decompiled_binary_matches_its_source_whatever_the_case_and_with_its_plain_values_keyed(self):
        self.assertEqual(compiled.round_trip(MODEL, BACK), [])

    def test_a_lost_or_changed_key_is_a_difference(self):
        lost = BACK.replace('            birthratekey 2\n                0.0 12.0\n                1.0 12.0\n', '')
        self.assertEqual(compiled.round_trip(MODEL, lost), ['animloop01/smoke: birthratekey only in the source'])
        changed = BACK.replace('1.0 12.0', '1.0 6.0')
        self.assertIn('values differ', ' '.join(compiled.round_trip(MODEL, changed)))
        moved = BACK.replace('0.0 1.0 2.0 3.0', '0.0 1.0 2.0 3.1')
        self.assertIn('position differs', ' '.join(compiled.round_trip(MODEL, moved)))

    def test_only_the_nodes_the_compiler_says_it_dropped_may_be_missing(self):
        gone = BACK.replace('''        node emitter smoke
            parent t_a01
            positionkey 1
                0.0 1.0 2.0 3.0
            birthratekey 2
                0.0 12.0
                1.0 12.0
        endnode
''', '')
        self.assertTrue(compiled.round_trip(MODEL, gone))
        warning = 'animation "animloop01": 1 animation node(s) are not connected to the root and were left out of the binary: Smoke'
        self.assertEqual(compiled.dropped_nodes([warning, 'something else']), {('animloop01', 'smoke')})
        self.assertEqual(compiled.round_trip(MODEL, gone, compiled.dropped_nodes([warning])), [])

    def test_a_bind_transform_moved_by_the_compile_is_a_difference(self):
        plain = 'node emitter smoke\n    parent t_a01\nendnode'
        moved = BACK.replace(plain, 'node emitter smoke\n    parent t_a01\n    position 0.0 0.5 0.0\nendnode')
        self.assertEqual(compiled.round_trip(MODEL, moved), ['smoke: bind position differs'])
        turned = BACK.replace(plain, 'node emitter smoke\n    parent t_a01\n    orientation 0.0 0.0 1.0 0.5\nendnode')
        self.assertEqual(compiled.round_trip(MODEL, turned), ['smoke: bind rotation differs'])

    def test_a_node_name_used_twice_is_told_apart(self):
        twice = MODEL.replace('node emitter Smoke\n  parent t_a01\n  birthrate 0\nendnode\n', 'node emitter Smoke\n  parent t_a01\nendnode\n' * 2, 1)
        self.assertEqual([name for _, name, _ in compiled.read_ascii(twice)['nodes']], ['t_a01', 'smoke', 'smoke#2'])


class PairTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory(); self.addCleanup(holder.cleanup); self.repo = Path(holder.name)
        (self.repo / 'sources' / 'srn_t_x').mkdir(parents=True); (self.repo / 'srn_t_x').mkdir()
        self.source = self.repo / 'sources' / 'srn_t_x' / 't_a01.mdl'; self.source.write_text(MODEL, encoding='ascii')
        self.binary = self.repo / 'srn_t_x' / 't_a01.mdl'; self.binary.write_bytes(b'\0\0\0\0binary')
        rows = {'srn_t_x/t_a01.mdl': {'source': sha(self.source.read_bytes()), 'binary': sha(self.binary.read_bytes())}}
        (self.repo / compiled.MANIFEST).write_text(json.dumps({'schemaVersion': 1, 'kind': compiled.KIND, 'materials': compiled.materials(self.repo), 'models': rows}),
                                                   encoding='utf-8')

    def test_a_material_changed_in_an_adopted_pack_makes_every_binary_stale(self):
        (self.repo / 'srn_t_x' / 'wall.mtr').write_text('renderhint NormalAndSpecMapped\ntexture0 wall\n', encoding='ascii')
        self.assertEqual(compiled.stale(self.repo), ['srn_t_x/t_a01.mdl'])
        self.assertIn('materials of srn_t_x changed', compiled.check(self.repo)[0])
        digest = compiled.materials(self.repo)
        (self.repo / 'srn_t_y').mkdir(); (self.repo / 'srn_t_y' / 'wall.mtr').write_text('other', encoding='ascii')  # a pack never adopted: no binary depends on it
        self.assertEqual(compiled.materials(self.repo), digest)
        (self.repo / 'sources' / 'srn_t_x' / 't_b01.mdl').write_text(MODEL, encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'compile every source'):  # one of two sources compiled would leave the other stale
            compiled.compile_models(self.repo, 'blender', 'addon', ['srn_t_x/t_a01.mdl'])

    def test_a_material_borrowed_from_another_pack_is_looked_up_and_digested(self):
        self.source.write_text(MODEL.replace('birthrate 0', 'birthrate 0\n  bitmap Manhole'), encoding='ascii')
        for pack in ('srn_door', 'srn_placeable'):
            (self.repo / pack).mkdir(); (self.repo / pack / 'manhole.mtr').write_text('renderhint NormalAndSpecMapped\n', encoding='ascii')
        (self.repo / 'srn_placeable' / 'unnamed.mtr').write_text('renderhint NormalAndSpecMapped\n', encoding='ascii')
        self.assertEqual(compiled.borrowed(self.repo), {'manhole.mtr': self.repo / 'srn_door' / 'manhole.mtr'})  # the first pack in hak order; one no source names is not
        digest = compiled.materials(self.repo); (self.repo / 'srn_door' / 'manhole.mtr').write_text('texture0 manhole\n', encoding='ascii')
        self.assertNotEqual(compiled.materials(self.repo), digest)

    def test_a_pair_the_manifest_pins_holds(self):
        self.assertEqual(compiled.check(self.repo), []); self.assertEqual(compiled.stale(self.repo), [])

    def test_a_source_changed_without_a_compile_is_caught(self):
        self.source.write_text(MODEL + '\n', encoding='ascii')
        self.assertEqual(compiled.check(self.repo), ['srn_t_x/t_a01.mdl: the source changed since it was compiled'])
        self.assertEqual(compiled.stale(self.repo), ['srn_t_x/t_a01.mdl'])

    def test_a_binary_changed_by_hand_or_a_source_never_compiled_is_caught(self):
        self.binary.write_bytes(b'\0\0\0\0other')
        self.assertIn('not the binary compiled from the source', compiled.check(self.repo)[0])
        (self.repo / 'sources' / 'srn_t_x' / 't_b01.mdl').write_text(MODEL, encoding='ascii')
        self.assertIn('srn_t_x/t_b01.mdl: not compiled (no row in sources/compiled.json)', compiled.check(self.repo))

    def test_the_tools_read_and_write_the_source_of_a_compiled_tile_model(self):
        self.assertEqual(compiled.source(self.repo, self.binary), self.source)
        self.assertEqual(compiled.source(self.repo, self.repo / 'srn_t_x' / 't_b01.mdl'), self.repo / 'srn_t_x' / 't_b01.mdl')  # no source kept
        self.assertEqual(compiled.source_target(self.repo, self.repo / 'srn_t_x' / 'new.mdl'), self.repo / 'sources' / 'srn_t_x' / 'new.mdl')
        self.assertEqual(compiled.source_target(self.repo, self.repo / 'srn_t_y' / 'new.mdl'), self.repo / 'srn_t_y' / 'new.mdl')  # a pack never adopted keeps ASCII
        self.assertEqual(compiled.source_target(self.repo, self.repo / 'srn_door' / 'd.mdl'), self.repo / 'srn_door' / 'd.mdl')  # no tile pack
        self.assertEqual(compiled.source_target(self.repo, self.repo / 'srn_t_x' / 't_a01.wok'), self.repo / 'srn_t_x' / 't_a01.wok')

    def test_adopting_moves_the_ascii_models_and_leaves_the_compiled_ones(self):
        (self.repo / 'srn_t_x' / 't_c01.mdl').write_text(MODEL, encoding='ascii'); (self.repo / 'srn_t_x' / 'ek_a.mdl').write_bytes(b'\0\0\0\0ek')
        self.binary.unlink(); self.source.unlink()
        self.assertEqual(compiled.adopt(self.repo, ['srn_t_x']), ['srn_t_x/t_c01.mdl'])
        self.assertTrue((self.repo / 'sources' / 'srn_t_x' / 't_c01.mdl').is_file()); self.assertTrue((self.repo / 'srn_t_x' / 'ek_a.mdl').is_file())
        self.assertTrue((self.repo / 'srn_t_x' / 't_c01.mdl').is_file())  # the pack keeps its copy until the compile replaces it
        self.assertEqual(compiled.adopt(self.repo, ['srn_t_x']), [])  # again, after a failed compile: nothing new to copy
        (self.repo / 'sources' / 'srn_t_x' / 't_c01.mdl').write_text(MODEL + '\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'differs from srn_t_x/t_c01.mdl'):
            compiled.adopt(self.repo, ['srn_t_x'])


class RepositoryTests(unittest.TestCase):
    def test_every_kept_source_has_the_binary_the_manifest_pins(self):
        self.assertEqual(sorted({key.split('/')[0] for key in compiled.sources(REPO)}), sorted(PACKS))  # a new pack with sources is named above
        self.assertEqual(compiled.BORROW, BORROWED)
        self.assertEqual(test_impact.SOURCES, compiled.SOURCES)  # CI checks out and guards the same folder
        self.assertEqual(compiled.check(REPO), [])

    def test_a_tile_pack_with_sources_ships_no_ascii_model(self):
        for pack in sorted({key.split('/')[0] for key in compiled.sources(REPO)}):
            ascii_models = [path.name for path in sorted((REPO / pack).glob('*.mdl')) if not inventory.compiled(path.read_bytes()[:4])]
            self.assertEqual(ascii_models, [], f'{pack} ships ASCII models: move them to sources/{pack} and compile them (tilekit compile --adopt)')


if __name__ == '__main__':
    unittest.main()
