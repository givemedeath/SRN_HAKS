"""The game settings every client run of tilekit states: the frame rate always limited (an uncapped client hung the
machine, 2026-11-19), keyholing off (it cuts holes in the walls being judged), and a camera that may look up."""
from . import require

MOST = 200  # frames a second at most, in any state of the window
CAMERA = '[camera]\nmode = 0\n[camera.limits]\nmax-pitch = 150.0\nmax-dist = 200.0\n'


def settings(foreground=60, background=30, *, stats=False, vsync=True):
    for cap in (foreground, background):
        require(isinstance(cap, int) and 1 <= cap <= MOST, f'A client runs with its frame rate limited, at 1 to {MOST} frames a second')
    text = (CAMERA + '[graphics.keyholing]\nenabled = false\n[graphics.framelimiter]\nenabled = true\n'
            f'[graphics.framelimiter.foreground]\ntarget-fps = {foreground}\n[graphics.framelimiter.background]\ntarget-fps = {background}\n'
            f'[graphics.framelimiter.non-interactive]\ntarget-fps = {background}\n')
    return text + ('[graphics.stats]\nenabled = true\n' if stats else '') + ('' if vsync else '[graphics.video.vsync]\nmode = "off"\n')
