"""The client check of a bake: a fixture spec made from the bake's folder, one actor per pose, the camera round each."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import client, poses, registry
from .test_tables import STOCK


def baked(folder, models=('chest', 'bicepl', 'bicepr'), compiled=True):
    """A bake's output folder: its record, and a resource per model."""
    folder = Path(folder)
    (folder / 'resources').mkdir(parents=True)
    names = {token: f'pmh0_{token}332' for token in models}
    for name in names.values():
        (folder / 'resources' / (name + '.mdl')).write_bytes(b'model')
    record = {'model': 'test', 'body': 'pmh0', 'tier': 2, 'number': 332, 'models': names}
    if compiled:
        record['compiled'] = len(names)
    (folder / 'bake.json').write_text(json.dumps(record), encoding='utf-8')
    return folder


def stock(folder):
    folder = Path(folder)
    folder.mkdir(parents=True)
    for table, text in STOCK.items():
        (folder / (table + '.2da')).write_bytes(text.encode('cp1252'))
    return folder


class PosesTests(unittest.TestCase):
    def test_a_part_token_belongs_to_one_slot(self):
        self.assertEqual([poses.slot_of(token) for token in ('chest', 'bicepr', 'shol', 'legl')], ['chest', 'bicep', 'shoulder', 'thigh'])
        with self.assertRaises(ValueError):
            poses.slot_of('wing')

    def test_the_spec_wears_the_outfit_in_every_pose_with_the_camera_round_each(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            document, layout = poses.spec(baked(root / 'bake', ('chest', 'bicepl', 'bicepr', 'shol', 'shor')), root / 'check', stock(root / 'stock'),
                                          [root / 'srn_body.hak'], preset='shoulders', without=['shoulder'])
            # the bake's resources and the parts tables with its entries, in the check's own folder
            made = sorted(path.name for path in (root / 'check' / 'resources').iterdir())
            self.assertIn('pmh0_chest332.mdl', made)
            self.assertIn('parts_chest.2da', made)
            self.assertIn('parts_shoulder.2da', made)
            self.assertEqual(document['resources'], str(root / 'check' / 'resources'))
            # one actor per pose, and beside each one without its shoulder pads
            self.assertEqual(len(document['actors']), 2 * len(poses.CAST))
            first, second = document['actors'][:2]
            self.assertEqual(first['parts'], {'bicep': 332, 'chest': 332, 'shoulder': 332})
            self.assertEqual(second['parts'], {'bicep': 332, 'chest': 332})
            self.assertEqual([actor['vars']['ANIM'] for actor in document['actors'][::2]], [animation for _, animation in poses.CAST])
            # four shots each, at the height of that pose's shoulders, labelled for the sheet
            views = poses.PRESETS['shoulders']['views']
            self.assertEqual(len(document['shots']), len(document['actors']) * len(views))
            self.assertEqual(layout['columns'], len(views))
            self.assertEqual(len(layout['labels']), len(document['shots']))
            crouching = [shot for shot in document['shots'] if document['actors'][shot['actor']]['label'].startswith('crouching')]
            self.assertTrue(crouching and all(shot['height'] == poses.PRESETS['shoulders']['heights']['crouching'] for shot in crouching))
            self.assertEqual(layout['labels'][len(views)], 'standing, without shoulder, shoulders front')
            self.assertNotIn('tlk', document)

    def test_a_bake_that_cannot_be_worn_is_refused_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            table = stock(root / 'stock')
            cases = [(baked(root / 'raw', compiled=False), {}),  # not compiled
                     (baked(root / 'one', ('chest', 'bicepl')), {}),  # one upper arm only
                     (baked(root / 'ok'), {'without': ['shoulder']}),  # no pads to leave off
                     (root / 'ok', {'preset': 'feet'})]
            for number, (bake_output, options) in enumerate(cases):
                with self.assertRaises(ValueError):
                    poses.spec(bake_output, root / f'check{number}', table, [], **options)
                self.assertFalse((root / f'check{number}').exists())
            partial = root / 'partial'  # a stock table missing: refused before the folder is made
            partial.mkdir()
            (partial / 'parts_chest.2da').write_bytes((table / 'parts_chest.2da').read_bytes())
            with self.assertRaises(OSError):
                poses.spec(root / 'ok', root / 'check-partial', partial, [])
            self.assertFalse((root / 'check-partial').exists())
            (root / 'used').mkdir()
            with self.assertRaises(ValueError):  # a fresh folder only
                poses.spec(root / 'ok', root / 'used', table, [])

    def test_the_entries_are_valid_registry_parts(self):
        checked = poses.entries(['chest', 'bicep'], 332, 2)
        self.assertEqual(sorted((part['slot'], part['number'], part['genderedCut']) for part in checked), [('bicep', 332, False), ('chest', 332, True)])
        self.assertTrue(all(set(part['tiers']) == set(registry.SLOT_JOINTS[part['slot']]) for part in checked))

    def test_waiting_for_the_client_needs_it_closed_twice_running(self):
        seen = iter([[7], [], [8], [], []])
        with mock.patch.object(client, 'running', lambda: next(seen)), mock.patch.object(client.time, 'sleep', lambda seconds: None):
            client.wait_free(100.0)
        self.assertEqual(list(seen), [])
        slept = []
        with mock.patch.object(client, 'running', lambda: []), mock.patch.object(client.time, 'sleep', slept.append):
            client.wait_free(3.0)  # a wait shorter than a poll: no client, so it is free once checked twice
        self.assertTrue(len(slept) == 1 and slept[0] <= 3.0)
        clock = iter(range(0, 1000, 5))
        with mock.patch.object(client, 'running', lambda: [7]), mock.patch.object(client.time, 'sleep', lambda seconds: None), \
                mock.patch.object(client.time, 'monotonic', lambda: float(next(clock))):
            with self.assertRaises(ValueError):  # another session's client is never closed
                client.wait_free(30.0)


if __name__ == '__main__':
    unittest.main()
