import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from tools.tilekit import perf

SHOTS = [{'area': 'a'}, {'area': 'a'}, {'area': 'b'}]


class PerfTest(unittest.TestCase):
    def test_load_screens_are_the_dark_stretches_after_the_first(self):
        frames = [(0.1, True), (0.2, True), (0.3, False), (5.0, True), (5.1, True), (6.2, True), (6.3, False), (9.0, True), (9.5, True)]
        self.assertEqual(perf.loads(frames), [{'from': 5.0, 'to': 6.2, 'seconds': 1.2}, {'from': 9.0, 'to': 9.5, 'seconds': 0.5}])
        dark = Image.new('RGB', (400, 225)); dark.paste((200, 200, 200), (120, 30, 280, 200)); self.assertTrue(perf.loading(dark))
        self.assertFalse(perf.loading(Image.new('RGB', (400, 225), (40, 40, 40))))

    def test_the_watch_grabs_only_round_an_area_change(self):
        with tempfile.TemporaryDirectory() as folder:
            now = [0.0]; log = Path(folder) / 'log.txt'; grabbed = []

            def grab(pid):
                grabbed.append(now[0]); return Image.new('RGB', (1600, 900))
            watch = perf.Watch(log, folder, SHOTS, arrive=20.0, hold=10.0, clock=lambda: now[0], running=lambda: [7], grab=grab)
            for at, line in ((0.5, None), (1.0, 'x ENVKIT shot=0 target=p valid=1\n'), (5.0, None), (11.0, 'x ENVKIT shot=1 target=q valid=1\n'), (12.0, None), (20.0, None), (40.0, None), (42.0, None)):
                now[0] = at
                if line:
                    with log.open('a') as file:
                        file.write(line)
                watch.step()
            self.assertEqual(grabbed, [0.5, 20.0, 40.0])  # the start, then from two seconds before view 1 ends until area b has had its time
            self.assertEqual([stamp for stamp, _ in watch.stamps], [1.0, 11.0]); self.assertEqual(watch.missed, 0)
            with log.open('a') as file:
                file.write('half a li')
            watch.step(); self.assertEqual(len(watch.stamps), 2)

    def test_refused_beside_a_client_or_without_a_limit(self):
        with mock.patch.object(perf.client, 'running', return_value=[1]), self.assertRaisesRegex(ValueError, 'client is running'):
            perf.run('.', {}, 'out', 'n', 'g', 'b')
        with mock.patch.object(perf.client, 'running', return_value=[]), self.assertRaisesRegex(ValueError, 'limited'):
            perf.run('.', {}, 'out', 'n', 'g', 'b', cap=0)

    def test_a_run(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'out'; shots = [{'area': 'a', 'label': 'day-x'}]

            def built(name, areas, shots, output, *_, **said):
                self.assertEqual((said['hold'], said['arrive']), (perf.HOLD, perf.ARRIVE)); out.mkdir(); return {'module': 'm.mod', 'userDirectory': str(out / 'user'), 'overlay': []}

            def ran(game, record, captures, **said):
                self.assertIn('target-fps = 200', said['extra_settings']); self.assertIn('[graphics.stats]\nenabled = true', said['extra_settings']); self.assertIn('keyholing]\nenabled = false', said['extra_settings'])
                captures.mkdir(); path = captures / 'shot-00-day-x.png'; Image.new('RGB', (1600, 900)).save(path); return {'captures': [str(path)], 'late': [], 'lines': []}
            with mock.patch.object(perf.client, 'running', return_value=[]), mock.patch.object(perf.family_review, 'plan', return_value=([], shots, [])), \
                    mock.patch.object(perf.review, 'build', built), mock.patch.object(perf.prop_fixture, 'run', ran):
                told = perf.run('.', {'tileset': 'dgt04'}, out, 'n', 'g', 'b')
            self.assertEqual((told['cap'], told['loads'], told['views']), (200, [], 1)); self.assertTrue((out / 'counters.png').is_file()); self.assertTrue((out / 'perf.json').is_file())


if __name__ == '__main__':
    unittest.main()
