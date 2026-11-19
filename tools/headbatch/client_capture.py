"""Unattended captures of the private head client, filed against the exact log events they show.

Ported from itemkit's client capture (tools/itemkit/client_capture.py, tools/armorkit/client.py): watch the private
client log, and after each camera placement (`HEAD_INSPECT actor=...`) or animation (`HEAD_MOTION`) save a short burst
of the client window's own pixels, whether or not it is in front. A burst that ran into the next logged event shows
the wrong view: its files are kept but never filed. Only the owned client's window, found by its process id, is read.

The result is evidence to review, never a review: `captures.json` (kind head-client-captures-v1, for
tools/heads/client_capture_review.py) binds each filed frame to its exact log event, and `sheet-HEAD.png` shows one
head's frames together. A person still inspects every frame (RUNBOOK 370: obscured, highlighted or wrong-pose frames
are rejected at review).
"""
import ctypes
import json
import re
import struct
import threading
import time
import zlib
from ctypes import wintypes
from pathlib import Path

from head_files import sha, write_json

# The coverage verifier's own log grammar (tools/heads/verify_head_trial.py SESSION, ENTRY, FIELDS).
SESSION = re.compile(r'^Messages for: (?P<started>.+?)\s*$')
ENTRY = re.compile(r'^\[[^\]]*\] (?P<text>.*)$')
FIELDS = re.compile(r'(\w+)=(\S+)')
VIEWS = ('three', 'threeleft', 'backright', 'backleft')
# Settling after the logged event (RUNBOOK 370): the repeated initial placement, later angles, the animation.
FIRST_SETTLE, SETTLE, MOTION_SETTLE = 1.5, 1.0, 1.6
FRAMES, GAP, POLL = 3, 0.3, 0.05
SRCCOPY, CAPTUREBLT, PW_RENDERFULLCONTENT = 0x00CC0020, 0x40000000, 2


def session_lines(text):
    """Entry texts after the newest 'Messages for:' banner, exactly as tools/heads/verify_head_trial.last_session parses
    them: filed event indices are positions in this list, server-option entries included (RUNBOOK 378)."""
    lines = []
    for line in text.splitlines():
        if SESSION.match(line):
            lines = []
            continue
        match = ENTRY.match(line)
        if match:
            lines.append(match['text'])
    return lines


def events(lines):
    """(index, kind, fields) for the camera placements and animations a burst can show."""
    found = []
    for index, line in enumerate(lines):
        if line.startswith('HEAD_INSPECT actor='):
            found.append((index, 'inspect', dict(FIELDS.findall(line))))
        elif line.startswith('HEAD_MOTION '):
            found.append((index, 'motion', dict(FIELDS.findall(line))))
    return found


def window(pid):
    """The owned client's visible, titled top-level window, or None while it has none."""
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    found = []

    @callback
    def visit(handle, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(handle) and user32.GetWindowTextLengthW(handle):
            found.append(handle)
        return True
    user32.EnumWindows(visit, 0)
    # The game window, not a small helper window the process also owns: the largest client area.
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))

    def area(handle):
        rect = wintypes.RECT()
        return (rect.right-rect.left)*(rect.bottom-rect.top) if user32.GetClientRect(handle, ctypes.byref(rect)) else 0
    return max(found, key=area) if found else None


class _BitmapInfo(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD), ('colors', wintypes.DWORD*3)]


def grab(handle, *, print_window=False):
    """The window's client-area pixels as (width, height, BGRA bytes): its own DC (as PIL.ImageGrab.grab(window=)
    reads it), or PrintWindow with full content for a renderer whose DC comes back blank."""
    user32, gdi32 = ctypes.WinDLL('user32'), ctypes.WinDLL('gdi32')
    for function in (user32.GetDC, gdi32.CreateCompatibleDC, gdi32.CreateCompatibleBitmap, gdi32.SelectObject):
        function.restype = wintypes.HANDLE
    user32.GetDC.argtypes = (wintypes.HWND,); user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HANDLE)
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.PrintWindow.argtypes = (wintypes.HWND, wintypes.HANDLE, wintypes.UINT)
    gdi32.CreateCompatibleDC.argtypes = (wintypes.HANDLE,)
    gdi32.CreateCompatibleBitmap.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_int)
    gdi32.SelectObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    gdi32.BitBlt.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HANDLE,
                             ctypes.c_int, ctypes.c_int, wintypes.DWORD)
    gdi32.GetDIBits.argtypes = (wintypes.HANDLE, wintypes.HANDLE, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.POINTER(_BitmapInfo), wintypes.UINT)
    gdi32.DeleteObject.argtypes = (wintypes.HANDLE,); gdi32.DeleteDC.argtypes = (wintypes.HANDLE,)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    if user32.IsIconic(handle):
        raise OSError('Client window is minimized; restore it so its frames render')
    rect = wintypes.RECT()
    if not user32.GetClientRect(handle, ctypes.byref(rect)):
        raise OSError('Client window has no client area')
    width, height = rect.right-rect.left, rect.bottom-rect.top
    if width < 64 or height < 64:
        raise OSError(f'Client window is too small to capture ({width}x{height})')
    source = user32.GetDC(handle)
    target = gdi32.CreateCompatibleDC(source)
    bitmap = gdi32.CreateCompatibleBitmap(source, width, height)
    old = gdi32.SelectObject(target, bitmap)
    try:
        done = (user32.PrintWindow(handle, target, PW_RENDERFULLCONTENT) if print_window else
                gdi32.BitBlt(target, 0, 0, width, height, source, 0, 0, SRCCOPY | CAPTUREBLT))
        if not done:
            raise OSError('Window capture failed')
        info = _BitmapInfo(); info.biSize = 40; info.biWidth = width; info.biHeight = -height
        info.biPlanes = 1; info.biBitCount = 32
        pixels = ctypes.create_string_buffer(width*height*4)
        if gdi32.GetDIBits(target, bitmap, 0, height, pixels, ctypes.byref(info), 0) != height:
            raise OSError('Window pixels could not be read')
        return width, height, pixels.raw
    finally:
        gdi32.SelectObject(target, old); gdi32.DeleteObject(bitmap); gdi32.DeleteDC(target)
        user32.ReleaseDC(handle, source)


def blank(width, height, bgra, step=997):
    """A frame with almost no variation (black, or one fill): what an unreadable surface returns."""
    channels = [bgra[offset::4*step] for offset in range(3)]
    return not channels[0] or all(max(values)-min(values) <= 6 for values in channels)


def write_png(path, width, height, bgra):
    """An 8-bit RGB PNG from top-down BGRA rows (no imaging dependency in the private session)."""
    rows = bytearray()
    stride = width*4
    for y in range(height):
        row = bgra[y*stride:(y+1)*stride]
        rgb = bytearray(width*3)
        rgb[0::3] = row[2::4]; rgb[1::3] = row[1::4]; rgb[2::3] = row[0::4]
        rows += b'\x00'+rgb

    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data) & 0xffffffff)
    data = (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(rows), 1))+chunk(b'IEND', b''))
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f'Preserve the existing capture {path}')
    path.write_bytes(data)
    return path


def frame(pid):
    """One frame of the owned client window as (width, height, BGRA, method); refuses a missing window or a blank
    surface. Encoding happens later, off the burst's clock."""
    handle = window(pid)
    if handle is None:
        raise OSError('The owned client has no window to capture')
    width, height, pixels = grab(handle)
    if not blank(width, height, pixels):
        return width, height, pixels, 'window-dc'
    width, height, pixels = grab(handle, print_window=True)
    if blank(width, height, pixels):
        raise OSError('The client window returned a blank frame')
    return width, height, pixels, 'print-window'


def save(path, captured):
    width, height, pixels, method = captured
    write_png(path, width, height, pixels)
    return {'path': Path(path).name, 'sha256': sha(path), 'width': width, 'height': height, 'method': method}


class Watcher(threading.Thread):
    """Capture a burst after each new camera placement or animation in the owned client's log."""

    def __init__(self, pid, log, folder, *, final=(), sleep=time.sleep, capture=frame, store=save):
        super().__init__(daemon=True)
        self.pid, self.log, self.folder, self.final = pid, Path(log), Path(folder), set(final)
        self.sleep, self.capture, self.store = sleep, capture, store
        self.stopping = threading.Event()
        self.encoding = threading.Lock()  # stop() may flush while a capture thread that outlived its join still does
        self.bursts, self.errors, self.pending = [], [], []
        self.started = time.time()
        self.cached = (None, [])

    def lines(self):
        """The current session's entries; nothing until the client has written this run's log (a previous run's log
        stays in place until the client rotates it at startup). Parsed again only when the log changes: it is polled
        every POLL seconds and grows to megabytes with cliententirelog."""
        try:
            status = self.log.stat()
            if status.st_mtime < self.started:
                return []
            stamp = (status.st_size, status.st_mtime_ns)
            if stamp != self.cached[0]:
                self.cached = (stamp, session_lines(self.log.read_text(encoding='utf-8', errors='replace')))
            return self.cached[1]
        except OSError:
            return []

    def newer(self, index):
        return any(event[0] > index for event in events(self.lines()))

    def run(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        seen, first = -1, True
        while not self.stopping.is_set():
            found = [event for event in events(self.lines()) if event[0] > seen]
            if not found:
                self.sleep(POLL); continue
            # Only the newest event's view is still on screen; earlier ones in the same read are gone.
            for index, kind, fields in found[:-1]:
                self.bursts.append({'event': index, 'kind': kind, 'fields': fields, 'frames': [], 'rejected': 'next event began'})
            index, kind, fields = found[-1]; seen = index
            settle = MOTION_SETTLE if kind == 'motion' else (FIRST_SETTLE if first else SETTLE)
            first = first and kind != 'inspect'
            self.sleep(settle)
            burst = {'event': index, 'kind': kind, 'fields': fields, 'frames': []}
            if self.newer(index):
                burst['rejected'] = 'next event began before the view settled'
                self.bursts.append(burst); continue
            raw = []
            try:
                for number in range(FRAMES):
                    raw.append(self.capture(self.pid))
                    if number < FRAMES-1:
                        self.sleep(GAP)
            except OSError as error:
                burst['rejected'] = f'capture failed: {error}'; self.errors.append(str(error))
            if self.newer(index) and 'rejected' not in burst:
                burst['rejected'] = 'next event began during the burst'  # files kept, never filed
            stem = f"{len(self.bursts):03d}-{kind}-{fields.get('actor', 'none')}-{fields.get('view', 'motion')}"
            self.pending.append((burst, stem, raw))
            self.bursts.append(burst)
            self.flush()

    def flush(self):
        """Encode captured frames. Runs between bursts: settling time leaves room for it."""
        with self.encoding:
            while self.pending:
                burst, stem, raw = self.pending.pop(0)
                for number, captured in enumerate(raw):
                    try:
                        burst['frames'].append(self.store(self.folder/f'{stem}-{number}.png', captured))
                    except OSError as error:
                        burst.setdefault('rejected', f'frame not saved: {error}'); self.errors.append(str(error))

    def complete(self):
        """The tour's last view is on file: the last head's motion burst, then a finished still of that head."""
        bursts = list(self.bursts)
        motion = [row['event'] for row in bursts if row['kind'] == 'motion' and row['fields'].get('actor') in self.final]
        return bool(motion) and any(row['kind'] == 'inspect' and row['event'] > motion[-1] and row['fields'].get('actor') in self.final
                                    for row in bursts)

    def stop(self, timeout=15):
        self.stopping.set()
        if self.is_alive():
            self.join(timeout)
        self.flush()


def final_tags(manifest):
    """Actor tags of the last head the tour shows (all of its looks)."""
    last = max(row['row'] for row in manifest['actors'])
    return [row['tag'] for row in manifest['actors'] if row['row'] == last]


def record(folder, bursts, errors):
    """The raw burst record, every frame pinned; written once."""
    return write_json(Path(folder)/'capture-record.json', {
        'kind': 'head-client-capture-bursts-v1', 'bursts': bursts, 'errors': errors,
        'settleSeconds': {'first': FIRST_SETTLE, 'view': SETTLE, 'motion': MOTION_SETTLE},
        'framesPerBurst': FRAMES, 'gapSeconds': GAP, 'reviewRequired': True})


def filed(manifest_path, log_path, folder, bursts):
    """A head-client-captures-v1 record from the accepted bursts: the last (most settled) frame of each burst.
    Primary-look stills at the four three-quarter views, every other accepted still (gameplay distance, the
    alternate look) and each motion frame, with the inspection that framed it. Evidence only."""
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    lines = session_lines(Path(log_path).read_text(encoding='utf-8', errors='replace'))
    actors = {row['tag'] for row in manifest['actors']}
    # The repeated initial placement: only its second entry can be filed (RUNBOOK 369).
    placements = [i for i, line in enumerate(lines) if line.startswith('HEAD_INSPECT actor=')][:2]
    warmup = placements[0] if len(placements) == 2 and lines[placements[0]] == lines[placements[1]] else None
    captures, last_inspect = [], {}
    for burst in sorted(bursts, key=lambda row: row['event']):
        index, fields = burst['event'], burst['fields']
        if index >= len(lines) or dict(FIELDS.findall(lines[index])) != fields:
            continue  # the archived log must show exactly the event this burst followed
        actor = fields.get('actor')
        if burst['kind'] == 'inspect':
            last_inspect[actor] = index
        if burst.get('rejected') or not burst['frames'] or actor not in actors or index == warmup:
            continue
        chosen = burst['frames'][-1]
        frame_pin = {'path': chosen['path'], 'sha256': chosen['sha256']}
        if burst['kind'] == 'motion':
            if actor in last_inspect:
                view = dict(FIELDS.findall(lines[last_inspect[actor]])).get('view')
                captures.append({'actor': actor, 'view': view, 'frame': frame_pin,
                                 'inspectionEvent': last_inspect[actor], 'motionEvent': index})
        else:
            captures.append({'actor': actor, 'view': fields.get('view'), 'frame': frame_pin, 'inspectionEvent': index,
                             'distance': fields.get('distance')})
    pin = lambda path: {'path': str(Path(path)), 'sha256': sha(path)}
    return write_json(Path(folder)/'captures.json', {
        'kind': 'head-client-captures-v1', 'manifest': pin(manifest_path), 'log': pin(log_path), 'captures': captures,
        'source': 'automatic window captures (tools/headbatch/client_capture.py)', 'visualReviewRequired': True})
