"""Run a fixture in the game client and collect its log lines and window captures.

Only a client this module started is ever stopped, and only by its process id. A client that is already
running blocks the run instead of being reused or closed.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

from .client_fixture import LOG_PREFIX
from .registry import require

PROCESS = 'nwmain.exe'
# A fresh user directory opens a 1024x768 window and pauses in the background; the fixture pins its own
# window size so captures are comparable and keeps the game running while another window is in front.
SETTINGS = ('[game.auto-pause.on-focus-loss]\nenabled = false\n[graphics.window]\nmode = "windowed"\n'
            '[graphics.window.windowed]\nwidth = {width}\nheight = {height}\n[ui]\nmouseover-feedback = false\n')
STAMP = re.compile(r'^\[[^\]]*\]\s*')


def command(nwn_root, user_directory, module):
    executable = Path(nwn_root) / 'bin' / 'win32' / PROCESS
    return [str(executable), '-userdirectory', str(Path(user_directory)), '+TestNewModule', module]


def running():
    """Process ids of every running client, ours or not."""
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + PROCESS, '/FO', 'CSV', '/NH'], capture_output=True, text=True)
    return [int(row.split('","')[1]) for row in result.stdout.splitlines() if row.lower().startswith('"' + PROCESS)]


def log_lines(user_directory, prefix=LOG_PREFIX):
    """The fixture's evidence lines from the client log, timestamps removed, in order."""
    path = Path(user_directory) / 'logs' / 'nwclientLog1.txt'
    if not path.is_file():
        return []
    found = []
    for line in path.read_text(encoding='cp1252', errors='replace').splitlines():
        text = STAMP.sub('', line.strip())
        if text.startswith(prefix):
            found.append(text)
    return found


def parse_line(line):
    """`ARMORKIT actor=A b=1 parts=1,2` -> {'actor': 'A', 'b': '1', 'parts': '1,2'}; values may hold spaces."""
    pairs = re.findall(r'(\w+)=(.*?)(?= \w+=|$)', line)
    return dict(pairs)


def start(nwn_root, user_directory, module, *, width=1600, height=900):
    require(sys.platform == 'win32', 'The client fixture runs on Windows')
    require(not running(), 'A game client is already running; it is not ours to reuse or close')
    user = Path(user_directory)
    settings = user / 'settings.tml'
    if not settings.exists():
        settings.write_text(SETTINGS.format(width=width, height=height), encoding='utf-8')
    log = user / 'logs' / 'nwclientLog1.txt'
    if log.exists():
        log.unlink()
    arguments = command(nwn_root, user, module)
    return subprocess.Popen(arguments, cwd=Path(arguments[0]).parent)


def window(pid):
    """The client's top-level window handle, or None while it has none."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(handle, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(handle) and user32.GetWindowTextLengthW(handle):
            found.append(handle)
        return True
    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def capture(pid, path):
    """Save the client window's own pixels, whether or not it is in front."""
    from PIL import ImageGrab
    handle = window(pid)
    require(handle is not None, 'The client has no window to capture')
    image = ImageGrab.grab(window=handle)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    image.convert('RGB').save(path)
    return Path(path)


def stop(process):
    """Close the client this module started. Takes the Popen from start(), never a bare name."""
    require(isinstance(process, subprocess.Popen), 'Only a client started here can be stopped')
    if process.poll() is None:
        subprocess.run(['taskkill', '/PID', str(process.pid), '/F'], capture_output=True)
        process.wait(timeout=30)


def run(nwn_root, record, captures, *, timeout=240, settle=1.5, until='done'):
    """Start the client on a built fixture, capture after each `shot=` line, stop it, and return the evidence.

    record: the dict fixture.build returned. captures: folder for the window captures."""
    user = record['userDirectory']
    process = start(nwn_root, user, Path(record['module']).stem)
    shots, seen = [], 0
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.5)
            require(process.poll() is None, 'The client exited before the fixture finished')
            lines = log_lines(user)
            for line in lines[seen:]:
                values = parse_line(line)
                if 'shot' in values and 'target' in values:
                    time.sleep(settle)
                    shots.append(str(capture(process.pid, Path(captures) / f'shot-{int(values["shot"]):02d}.png')))
            seen = len(lines)
            if any(line == f'{LOG_PREFIX} {until}' for line in lines):
                break
        else:
            raise ValueError('The fixture did not finish within the timeout')
        return {'lines': log_lines(user), 'captures': shots}
    finally:
        stop(process)
