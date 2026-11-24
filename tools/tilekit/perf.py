"""Frame rates and load times of a tileset's areas in the client, for comparing before and after.

The areas and views are a family review's (`family_review.plan`). The run holds each view long enough for the game's own
frame counter to settle, with vsync off and every frame limiter at one cap (200 at most: an uncapped client hung the
machine, and a cap that is reached says only that the rate is at least that). The counter's corner of every capture is
put on one sheet, `counters.png`, to be read by eye. While the client loads another area its window is grabbed every
`EVERY` seconds: a load screen is black outside its picture, so the stretch of frames with dark margins is the load.
What is dark before the first view is the client starting, and is left out. Frames, log lines with the time each was seen, and what was
measured are kept in the run's folder (`perf.json`). A run is refused while another client is up: it would measure both."""
import json
import threading
import time
from pathlib import Path

from tools.armorkit import client
from tools.envkit import prop_fixture

from . import family_review, require, review
from .client_settings import MOST as CAP, settings

ARRIVE, HOLD, SETTLE = 25.0, 14.0, 9.0  # seconds: for an area to load, each view is held, and its counter settles before the capture
EVERY, POLL, LOOK = 0.1, 0.02, 1.0  # seconds between grabs, between looks at the log, and between looks for the client
GAP = 8.0  # seconds without a frame that are a pause in the grabbing (a stalled grab is shorter)
LEAD = 2.0  # seconds before a view ends that grabbing begins
DARK = 12  # the brightest a load screen's margins are, of 255
COUNTER = (1340, 0, 1600, 90)  # the counter's corner of a 1600 x 900 capture
SHOT = prop_fixture.LOG_PREFIX + ' shot='


class Watch(threading.Thread):
    """Notes each log line with the time it is first seen, and grabs the window round a change of area."""

    def __init__(self, log, frames, shots, *, arrive=ARRIVE, hold=HOLD, clock=time.monotonic, running=client.running, grab=client.grab, sleep=time.sleep):
        super().__init__(daemon=True)
        self.log, self.frames, self.shots, self.arrive, self.hold, self.clock, self.running, self.grab, self.sleep = Path(log), Path(frames), shots, arrive, hold, clock, running, grab, sleep
        self.stamps, self.missed, self.done, self.began = [], 0, threading.Event(), clock()
        self._seen, self._pid, self._last, self._looked, self._from, self._until = 0, None, -EVERY, -LOOK, 0.0, float('inf')

    def step(self):
        now = self.clock() - self.began
        if self.log.is_file():
            lines = self.log.read_text(encoding='latin-1').splitlines(keepends=True); whole = [line.rstrip('\r\n') for line in lines if line.endswith('\n')]  # a line half written is read again
            for line in whole[self._seen:]:
                self.stamps.append((round(now, 3), line))
                if SHOT in line:  # frames only round an area change: from the last view's end through the arrival
                    number = int(line.split('shot=')[1].split()[0])
                    changes = number + 1 < len(self.shots) and self.shots[number + 1]['area'] != self.shots[number]['area']
                    self._from, self._until = (now + self.hold - LEAD, now + self.hold + self.arrive) if changes else (float('inf'), 0.0)
            self._seen = len(whole)
        if self._pid is None and now - self._looked >= LOOK:
            self._looked = now; found = self.running(); self._pid = found[0] if found else None
        if self._pid is not None and self._from <= now <= self._until and now - self._last >= EVERY:
            self._last = now
            try:
                image = self.grab(self._pid); image.thumbnail((400, 225)); image.convert('RGB').save(self.frames / f'{now:07.2f}.jpg', quality=70)
            except (ValueError, OSError):  # no window yet, or it is closing
                self.missed += 1

    def run(self):
        while not self.done.is_set():
            try:
                self.step()
            except (ValueError, OSError):  # the log is being written, or tasklist failed once
                self.missed += 1
            self.sleep(POLL)

    def finish(self):
        self.done.set(); self.join()


def loading(image):
    """Whether a frame is a load screen: dark left and right of its picture."""
    image = image.convert('L'); width, height = image.size
    return max(max(image.crop((0, 0, int(width * 0.25), height)).getextrema()), max(image.crop((int(width * 0.75), int(height * 0.15), width, height)).getextrema())) <= DARK


def loads(frames, after=0.0):
    """[{from, to, seconds, ended}] of the load screens in [(time, is a load screen)] that begin after `after` (the first view:
    until then the client is starting). A stretch ends where grabbing paused (`GAP`); `ended` is false where no frame after it was seen lit: the load
    took longer than the grabbing, or the view itself is that dark."""
    found, start, last = [], None, None
    for at, dark in sorted(frames):
        if start is not None and (not dark or at - last > GAP):
            found.append((start, last, at - last <= GAP)); start = None
        if dark and start is None:
            start = at
        last = at
    if start is not None:
        found.append((start, last, False))
    return [{'from': begin, 'to': end, 'seconds': round(end - begin, 2), 'ended': ended} for begin, end, ended in found if begin > after]


def counters(captures, output):
    """One sheet of the captures' counters, each under its view's name."""
    from PIL import Image, ImageDraw
    captures = [Path(one) for one in captures]; require(captures, 'No captures to read a counter from'); wide, high = COUNTER[2] - COUNTER[0], COUNTER[3] - COUNTER[1]
    page = Image.new('RGB', (2 * wide, -(-len(captures) // 2) * (high + 14)), 'white'); draw = ImageDraw.Draw(page)
    for index, path in enumerate(captures):
        x, y = index % 2 * wide, index // 2 * (high + 14); draw.text((x + 2, y + 1), path.stem, fill='black')
        with Image.open(path) as picture:
            page.paste(picture.crop(COUNTER), (x, y + 14))
    page.resize((page.width * 2, page.height * 2)).save(output)
    return len(captures)


def run(repo, spec, out, name, game, built, *, overlay=None, base='.', views=None, most=family_review.MOST, cap=CAP):
    """Build the areas, run the client over their views and write perf.json. Returns what it holds."""
    extra = settings(cap, cap, stats=True, vsync=False); require(not client.running(), 'A game client is running; frame rates measured beside it would be of both')  # before anything is built
    out = Path(out); areas, shots, left = family_review.plan(repo, spec, overlay=overlay, base=base, views=views, most=most)
    record = review.build(name, areas, shots, out, game, built, overlay=overlay, haks=family_review.haks(spec, repo), hold=HOLD, arrive=ARRIVE)
    frames = out / 'frames'; frames.mkdir(); watch = Watch(Path(record['userDirectory']) / 'logs' / 'nwclientLog1.txt', frames, shots); watch.start()
    try:
        result = prop_fixture.run(game, record, out / 'captures', settle=SETTLE, extra_settings=extra, late_ok=True)
    finally:
        watch.finish()
    from PIL import Image
    seen = []
    for path in frames.glob('*.jpg'):
        with Image.open(path) as picture:
            seen.append((float(path.stem), loading(picture)))
    first = next((at for at, line in watch.stamps if SHOT in line), float('inf'))  # no view: nothing was loaded for one
    told = {'module': record['module'], 'cap': cap, 'overlay': record['overlay'], 'views': len(shots), 'leftOut': left, 'captures': result['captures'], 'late': result['late'],
            'elsewhere': review.elsewhere(result['lines']), 'loads': loads(seen, first), 'frames': len(seen), 'grabsMissed': watch.missed, 'stamps': watch.stamps}
    if result['captures']:
        counters(result['captures'], out / 'counters.png')
    (out / 'perf.json').write_text(json.dumps(told, indent=1) + '\n', encoding='utf-8', newline='\n')
    return told
