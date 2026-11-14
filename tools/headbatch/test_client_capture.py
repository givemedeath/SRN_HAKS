"""Automatic private-client captures: event binding, rejected bursts, filing and the tour's end (RUNBOOK 375)."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import client_capture  # noqa: E402
import client_trial  # noqa: E402

ENTER = '[Fri Nov 13 10:00:00] HEAD_FIXTURE_CLIENT_ENTER'


def inspect(actor, view, distance='1.50'):
    return f'[Fri Nov 13 10:00:01] HEAD_INSPECT actor={actor} view={view} height=1.81 distance={distance} offset=0.000'


def motion(actor):
    return f'[Fri Nov 13 10:00:02] HEAD_MOTION actor={actor} sequence=talk-look'


class Timeline:
    """A fake clock: sleeping writes every log line whose time has come, and stops the watcher at the end."""

    def __init__(self, log, schedule, watcher=None):
        self.log, self.schedule, self.now, self.watcher, self.written = log, sorted(schedule), 0.0, watcher, 0
        self.log.write_text(ENTER+'\n', encoding='utf-8')

    def sleep(self, seconds):
        self.now += seconds
        due = [line for at, line in self.schedule if at <= self.now]
        if len(due) > self.written:
            with self.log.open('a', encoding='utf-8') as handle:
                handle.write(''.join(line+'\n' for line in due[self.written:]))
            self.written = len(due)
        if self.now > self.schedule[-1][0]+5:
            self.watcher.stopping.set()


def fake_capture(pid):
    return (64, 64, bytes(range(256))*64, 'window-dc')


def fake_store(path, captured):
    Path(path).write_bytes(b'frame'+path.name.encode())
    return {'path': Path(path).name, 'sha256': client_capture.sha(path), 'width': 64, 'height': 64, 'method': captured[3]}


def watch(folder, schedule, final=()):
    log = folder/'nwclientLog1.txt'
    watcher = client_capture.Watcher(1, log, folder/'captures', final=final, capture=fake_capture, store=fake_store)
    timeline = Timeline(log, schedule, watcher)
    watcher.sleep = timeline.sleep
    watcher.started = 0
    watcher.run()
    watcher.flush()
    return watcher, log


class CaptureTests(unittest.TestCase):
    def test_events_follow_the_last_session_without_timestamps(self):
        lines = client_capture.session_lines('\n'.join([ENTER, inspect('a0', 'three'), ENTER, inspect('a1', 'backleft'), motion('a1')]))
        self.assertEqual([kind for _, kind, _ in client_capture.events(lines)], ['inspect', 'motion'])
        self.assertEqual(client_capture.events(lines)[0][2]['actor'], 'a1')

    def test_repeated_first_placement_files_only_the_second_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            # The client logs the first placement twice, one second apart (RUNBOOK 120, 369).
            watcher, log = watch(folder, [(1.0, inspect('sr_h_actor0', 'three')), (2.0, inspect('sr_h_actor0', 'three')),
                                          (8.5, inspect('sr_h_actor0', 'threeleft'))])
            first, second, third = watcher.bursts
            self.assertIn('next event began', first['rejected'])
            self.assertNotIn('rejected', second)
            self.assertEqual(len(second['frames']), client_capture.FRAMES)
            manifest = folder/'runtime-manifest.json'
            manifest.write_text(json.dumps({'actors': [{'tag': 'sr_h_actor0', 'headId': 'h', 'row': 0, 'column': 0}]}))
            client_capture.filed(manifest, log, folder/'captures', watcher.bursts)
            record = json.loads((folder/'captures'/'captures.json').read_text())
            self.assertEqual(record['kind'], 'head-client-captures-v1')
            self.assertEqual([(row['view'], row['inspectionEvent']) for row in record['captures']], [('three', 2), ('threeleft', 3)])
            self.assertEqual(record['captures'][0]['frame']['path'], second['frames'][-1]['path'])

    def test_a_burst_overrun_by_the_next_view_is_kept_but_never_filed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            watcher, log = watch(folder, [(1.0, inspect('sr_h_actor0', 'three')), (2.8, inspect('sr_h_actor0', 'backright'))])
            overrun = watcher.bursts[0]
            self.assertEqual(overrun['rejected'], 'next event began during the burst')
            self.assertTrue(overrun['frames'])
            self.assertTrue(all((folder/'captures'/frame['path']).is_file() for frame in overrun['frames']))
            manifest = folder/'runtime-manifest.json'
            manifest.write_text(json.dumps({'actors': [{'tag': 'sr_h_actor0', 'headId': 'h', 'row': 0, 'column': 0}]}))
            client_capture.filed(manifest, log, folder/'captures', watcher.bursts)
            views = [row['view'] for row in json.loads((folder/'captures'/'captures.json').read_text())['captures']]
            self.assertEqual(views, ['backright'])

    def test_motion_is_filed_with_the_inspection_that_framed_it_and_ends_the_tour(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            watcher, log = watch(folder, [(1.0, inspect('sr_h_actor0', 'front', '2.62')), (4.0, motion('sr_h_actor0')),
                                          (9.0, inspect('sr_h_actor1', 'front'))], final=['sr_h_actor0', 'sr_h_actor1'])
            self.assertTrue(watcher.complete())
            manifest = folder/'runtime-manifest.json'
            manifest.write_text(json.dumps({'actors': [{'tag': 'sr_h_actor0', 'headId': 'h', 'row': 0, 'column': 0},
                                                       {'tag': 'sr_h_actor1', 'headId': 'h', 'row': 0, 'column': 1}]}))
            client_capture.filed(manifest, log, folder/'captures', watcher.bursts)
            rows = json.loads((folder/'captures'/'captures.json').read_text())['captures']
            moving = [row for row in rows if 'motionEvent' in row]
            self.assertEqual([(row['inspectionEvent'], row['motionEvent']) for row in moving], [(1, 2)])
            self.assertEqual(len({row['frame']['sha256'] for row in rows}), len(rows))

    def test_the_tour_is_not_complete_before_the_last_heads_final_still(self):
        watcher = client_capture.Watcher(1, 'log', 'out', final=['last'])
        watcher.bursts = [{'event': 3, 'kind': 'motion', 'fields': {'actor': 'last'}}]
        self.assertFalse(watcher.complete())
        watcher.bursts.append({'event': 4, 'kind': 'inspect', 'fields': {'actor': 'other'}})
        self.assertFalse(watcher.complete())
        self.assertEqual(client_capture.final_tags({'actors': [{'tag': 'a', 'row': 0}, {'tag': 'b', 'row': 1}, {'tag': 'c', 'row': 1}]}), ['b', 'c'])

    def test_a_previous_runs_log_is_ignored_until_the_client_rewrites_it(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp)/'nwclientLog1.txt'
            log.write_text(ENTER+'\n'+inspect('old', 'three')+'\n', encoding='utf-8')
            watcher = client_capture.Watcher(1, log, Path(temp)/'captures')
            watcher.started = log.stat().st_mtime+60
            self.assertEqual(watcher.lines(), [])

    def test_png_writer_and_blank_frames(self):
        width, height = 70, 66
        pixels = bytes((x*3 % 256, y*5 % 256, (x+y) % 256, 255)[c] for y in range(height) for x in range(width) for c in range(4))
        self.assertFalse(client_capture.blank(width, height, pixels, step=7))
        self.assertTrue(client_capture.blank(width, height, bytes(width*height*4)))
        with tempfile.TemporaryDirectory() as temp:
            path = client_capture.write_png(Path(temp)/'f.png', width, height, pixels)
            with self.assertRaises(FileExistsError):
                client_capture.write_png(path, width, height, pixels)
            try:
                from PIL import Image
            except ImportError:
                self.skipTest('PIL is not on the test path')
            with Image.open(path) as image:
                self.assertEqual(image.size, (width, height))
                self.assertEqual(image.getpixel((5, 7)), (pixels[(7*width+5)*4+2], pixels[(7*width+5)*4+1], pixels[(7*width+5)*4]))

    def test_supervise_closes_a_finished_tour_as_completed(self):
        class Budget:
            def sample(self): pass
            def check(self): pass
        with tempfile.TemporaryDirectory() as temp:
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
            result = client_trial.supervise(child, Budget(), Path(temp)/'STOP', sleep=lambda s: None, finished=lambda: True)
            self.assertTrue(result['tourComplete'])
            self.assertIsNone(result['stopReason'])
            self.assertIsNotNone(child.poll())


if __name__ == '__main__':
    unittest.main()
