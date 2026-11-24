import tempfile
import unittest
from pathlib import Path

from tools.tilekit import repair

HEAD = """newmodel t
beginmodelgeom t
node dummy t
  parent NULL
endnode
node dummy arm
  parent t
endnode
endmodelgeom t
"""
SOUND = HEAD + """newanim on t
  length 1.0
  node dummy t
    parent NULL
  endnode
  node dummy arm
    parent t
    positionkey
      0.0 0 0 0
    endlist
  endnode
doneanim on t
donemodel t
"""


class RepairTest(unittest.TestCase):
    def test_a_sound_model_is_left_to_the_byte(self):
        for text in (SOUND, SOUND.replace('\n', '\r\n')):
            self.assertEqual(repair.repaired(text)[0], text)

    def test_unclosed_unparented_and_misspelled(self):
        broken = SOUND.replace('    endlist\n  endnode\ndoneanim', '    e n d l i s t\n\ndoneanim').replace('  node dummy arm\n    parent t\n', '  node dummy arm\n')
        new, told = repair.repaired(broken)
        self.assertEqual(new, SOUND.replace('doneanim', '\ndoneanim'))
        self.assertEqual((told['closed'], told['parented'], told['spelled']), (1, 1, 1))
        self.assertEqual(repair.repaired(new)[0], new)

    def test_a_same_repeat_goes_and_a_differing_one_stays(self):
        node = '  node dummy arm\n    parent t\n  endnode\n'
        text = SOUND.replace('  node dummy arm\n    parent t\n    positionkey\n      0.0 0 0 0\n    endlist\n  endnode\n', node + node + node.replace('    parent t\n', '    parent t\n    alphakey\n      0 1\n    endlist\n'))
        new, told = repair.repaired(text)
        self.assertEqual(told['dropped'], 1); self.assertEqual(told['differing'], [['on', 'arm']])
        self.assertEqual(new, text.replace(node + node, node))

    def test_a_node_without_a_geometry_parent_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, 'ghost'):
            repair.repaired(SOUND.replace('  node dummy arm\n    parent t\n', '  node dummy ghost\n'))
        with self.assertRaisesRegex(ValueError, 'doneanim'):
            repair.repaired(SOUND.replace('doneanim on t\n', ''))

    def test_writes_the_source_only_when_told(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder); (repo / 'srn_t_x').mkdir(); (repo / 'sources' / 'srn_t_x').mkdir(parents=True); (repo / 'srn_2da').mkdir()
            (repo / 'srn_t_x' / 'x.set').write_text('[TILE0]\nModel=t\n'); (repo / 'srn_t_x' / 't.mdl').write_bytes(b'\0\0\0\0binary')
            source = repo / 'sources' / 'srn_t_x' / 't.mdl'; broken = SOUND.replace('    endlist\n  endnode\n', '    endlist\n').encode(); source.write_bytes(broken)
            self.assertEqual(repair.repair(repo, 'x')['t']['closed'], 1); self.assertEqual(source.read_bytes(), broken)
            repair.repair(repo, 'x', models=['T'], write=True)
            self.assertEqual(source.read_bytes().decode(), SOUND); self.assertEqual((repo / 'srn_t_x' / 't.mdl').read_bytes()[:4], b'\0\0\0\0')
            self.assertEqual(repair.repair(repo, 'x'), {})
            with self.assertRaisesRegex(ValueError, 'nothere'):
                repair.repair(repo, 'x', models=['nothere'])


if __name__ == '__main__':
    unittest.main()
