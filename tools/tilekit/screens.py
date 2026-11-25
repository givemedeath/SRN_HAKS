"""Computer screens of the 2070s, drawn in code, and laid into the pictures of old devices.

The d20 Modern and UDP placeables carry the screenshots of their day: a Windows desktop on the office monitors, a
cartoon on the televisions, a British road map on a terminal (user, 2026-11-25: redraw any computer screen so it matches the setting). An image
model asked for a bare screen draws a device round it and leaves the screen dim (the first redraws of 2026-11-25), so a
screen is drawn here: bright lines on near-black, edge to edge, the same every time.

A screen list (docs/placeables/screens.json) is a material spec whose textures also have `screen`: a list of parts,
each with a `box` [left, top, right, bottom] in shares of the picture and one of
 draw   one of KINDS, with a `seed`, drawn over the box
 sign   a word in a panel: {text, colour, on}
 mend   true: the box is filled in from its own edges (a maker's logo taken off a plain surface)
`turn` (quarter turns anticlockwise) is for a screen that lies on its side in the picture. `dim` (0-1) is a worn one's.
`build` lays the parts on the enlarged picture and leaves what `redraw` would leave, so `material --redrawn` takes it."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from . import enlarge, material, require

BACK, CYAN, AMBER, GREEN, PINK, WHITE = (7, 11, 18), (72, 222, 238), (255, 178, 64), (92, 236, 132), (238, 78, 176), (214, 236, 242)
OVER = 3  # drawn this many times too large, then reduced: smooth lines


def _mix(colour, share, back=BACK):
    return tuple(int(b + (c - b) * share) for c, b in zip(colour, back))


class _Pen:
    """A drawing surface in shares of its own box: x and y run 0 to 1, whatever the size in pixels."""

    def __init__(self, width, height, seed):
        from PIL import Image, ImageDraw
        self.size = (max(width, 1) * OVER, max(height, 1) * OVER); self.image = Image.new('RGB', self.size, BACK); self.on = ImageDraw.Draw(self.image); self.rng = np.random.default_rng(seed)
        self.unit = max(min(self.size) / 256, 1.0)

    def at(self, x, y):
        return x * (self.size[0] - 1), y * (self.size[1] - 1)

    def line(self, points, colour, width=1.0):
        self.on.line([self.at(*point) for point in points], fill=colour, width=max(1, round(width * self.unit)), joint='curve')

    def box(self, x0, y0, x1, y1, fill=None, outline=None, width=1.0):
        a, b = self.at(x0, y0), self.at(x1, y1)
        if b[0] >= a[0] and b[1] >= a[1]:
            self.on.rectangle((*a, *b), fill=fill, outline=outline, width=max(1, round(width * self.unit)))

    def dot(self, x, y, radius, colour, outline=None, width=1.0):
        (cx, cy), r = self.at(x, y), radius * min(self.size); self.on.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour, outline=outline, width=max(1, round(width * self.unit)))

    def marks(self, x0, y0, x1, y1, rows, colour, fill=0.75):
        """Lines of marks that look like text and are none."""
        step = (y1 - y0) / rows
        for row in range(rows):
            x, y = x0, y0 + row * step; end = x0 + (x1 - x0) * (fill + (1 - fill) * self.rng.random()) * (0.45 if self.rng.random() < 0.2 else 1)
            while x < end:
                wide = (x1 - x0) * (0.015 + 0.06 * self.rng.random()); self.box(x, y + step * 0.2, min(x + wide, end), y + step * 0.62, fill=_mix(colour, 0.45 + 0.5 * self.rng.random())); x += wide + (x1 - x0) * 0.02

    def grid(self, x0, y0, x1, y1, across, down, colour):
        for index in range(across + 1):
            x = x0 + (x1 - x0) * index / across; self.line([(x, y0), (x, y1)], colour, 0.6)
        for index in range(down + 1):
            y = y0 + (y1 - y0) * index / down; self.line([(x0, y), (x1, y)], colour, 0.6)

    def pane(self, x0, y0, x1, y1, colour=CYAN):
        self.box(x0, y0, x1, y1, fill=_mix(colour, 0.06), outline=_mix(colour, 0.75), width=1.2); self.box(x0, y0, x0 + (x1 - x0) * 0.36, y0 + 0.018, fill=colour)

    def bars(self, x0, y0, x1, y1, count, colours):
        wide = (x1 - x0) / count
        for index in range(count):
            high = (y1 - y0) * (0.15 + 0.85 * self.rng.random()); self.box(x0 + index * wide, y1 - high, x0 + (index + 0.65) * wide, y1, fill=colours[index % len(colours)])

    def wave(self, x0, y0, x1, y1, colour, turns, width=1.6):
        phase = self.rng.random(4) * 6.28; middle, reach = (y0 + y1) / 2, (y1 - y0) / 2; points = []
        for index in range(161):
            s = index / 160; value = sum(math.sin(s * 6.28 * turns * rate + phase[n]) * share for n, (rate, share) in enumerate(((1, .5), (2.3, .25), (5.1, .17), (9.7, .08))))
            points.append((x0 + (x1 - x0) * s, middle - value * reach))
        self.line(points, colour, width)

    def network(self, x0, y0, x1, y1, count, colours):
        at = np.column_stack([x0 + (x1 - x0) * self.rng.random(count), y0 + (y1 - y0) * self.rng.random(count)])
        for index, point in enumerate(at):
            for other in np.argsort(((at - point) ** 2).sum(1))[1:4]:
                self.line([tuple(point), tuple(at[other])], _mix(colours[index % len(colours)], 0.45), 0.9)
        for index, point in enumerate(at):
            self.dot(*point, 0.006 + 0.012 * self.rng.random(), colours[index % len(colours)])

    def done(self, width, height):
        from PIL import Image
        return np.asarray(self.image.resize((width, height), Image.LANCZOS))


def _block(pen, x0, y0, x1, y1, colour=CYAN, cells=5):
    """A city block in wireframe, seen from above its corner."""
    point = lambda a, b, z: (x0 + (x1 - x0) * (0.5 + (a - b) / (2 * cells)), y1 - (y1 - y0) * (0.04 + (a + b) / (2 * cells) * 0.45 + z * 0.45))
    for a in range(cells, 0, -1):
        for b in range(cells, 0, -1):
            high = 0.1 + 0.85 * pen.rng.random() ** 2; p, q, r, s = (a - .85, b - .85), (a - .15, b - .85), (a - .15, b - .15), (a - .85, b - .15); tone = AMBER if pen.rng.random() < 0.12 else colour
            for side in ((p, q), (p, s)):
                pen.on.polygon([pen.at(*point(*side[0], 0)), pen.at(*point(*side[1], 0)), pen.at(*point(*side[1], high)), pen.at(*point(*side[0], high))], fill=_mix(tone, 0.1))
            top = [point(*corner, high) for corner in (p, q, r, s, p)]; pen.on.polygon([pen.at(*corner) for corner in top], fill=_mix(tone, 0.22)); pen.line(top, _mix(tone, 0.95), 0.8)
            for corner in (p, q, s):
                pen.line([point(*corner, 0), point(*corner, high)], _mix(tone, 0.7), 0.8)


def desktop(pen):
    pen.grid(0, 0, 1, 1, 16, 10, _mix(CYAN, 0.07)); pen.network(0.02, 0.04, 0.98, 0.86, 26, [_mix(CYAN, 0.3), _mix(AMBER, 0.25)])
    pen.pane(0.04, 0.06, 0.46, 0.56); _block(pen, 0.06, 0.1, 0.44, 0.54)
    pen.pane(0.5, 0.06, 0.96, 0.36, AMBER); pen.network(0.53, 0.11, 0.93, 0.33, 22, [AMBER, WHITE])
    pen.pane(0.5, 0.41, 0.72, 0.84); pen.marks(0.52, 0.45, 0.7, 0.82, 12, CYAN)
    pen.pane(0.75, 0.41, 0.96, 0.84, GREEN); pen.bars(0.77, 0.47, 0.95, 0.63, 8, [GREEN, _mix(GREEN, 0.6)]); pen.wave(0.77, 0.66, 0.95, 0.82, AMBER, 2)
    pen.pane(0.04, 0.61, 0.46, 0.84, PINK); pen.marks(0.06, 0.65, 0.44, 0.82, 6, PINK)
    pen.box(0, 0.91, 1, 1, fill=_mix(CYAN, 0.16)); pen.line([(0, 0.91), (1, 0.91)], CYAN, 1.2)
    for index in range(9):
        colour = (CYAN, AMBER, GREEN, PINK)[index % 4]; x = 0.05 + index * 0.06
        (pen.dot(x, 0.955, 0.02, None, colour, 1.6) if index % 2 else pen.box(x - 0.015, 0.935, x + 0.015, 0.975, outline=colour, width=1.6))
    pen.marks(0.82, 0.925, 0.97, 0.985, 2, WHITE)


def server(pen):
    pen.grid(0, 0, 1, 1, 12, 12, _mix(GREEN, 0.06)); pen.pane(0.04, 0.05, 0.6, 0.95, GREEN); pen.marks(0.07, 0.1, 0.58, 0.93, 22, GREEN)
    for index in range(2):
        pen.pane(0.65, 0.05 + index * 0.25, 0.96, 0.26 + index * 0.25, AMBER); pen.wave(0.67, 0.09 + index * 0.25, 0.94, 0.24 + index * 0.25, AMBER, 2 + index)
    for row in range(6):
        for column in range(6):
            pen.box(0.66 + column * 0.05, 0.58 + row * 0.06, 0.695 + column * 0.05, 0.615 + row * 0.06, fill=AMBER if pen.rng.random() < 0.15 else _mix(GREEN, 0.35 + 0.65 * pen.rng.random()))


def wave(pen):
    pen.grid(0.05, 0.06, 0.95, 0.94, 18, 14, _mix(GREEN, 0.14)); pen.wave(0.05, 0.12, 0.84, 0.5, GREEN, 3, 2.2); pen.wave(0.05, 0.18, 0.84, 0.46, _mix(CYAN, 0.6), 5); pen.bars(0.05, 0.58, 0.84, 0.92, 26, [AMBER, _mix(AMBER, 0.7)])
    for row in range(9):
        pen.dot(0.91, 0.12 + row * 0.095, 0.018, (GREEN, AMBER, CYAN)[row % 3])
    pen.box(0.02, 0.03, 0.98, 0.97, outline=CYAN, width=1.6)


def plan(pen):
    xs, ys = np.sort(pen.rng.random(11)), np.sort(pen.rng.random(9))
    for x in xs:
        pen.line([(x, 0), (x + 0.1 * (pen.rng.random() - .5), 1)], _mix(CYAN, 0.4), 1.2)
    for y in ys:
        pen.line([(0, y), (1, y + 0.1 * (pen.rng.random() - .5))], _mix(CYAN, 0.4), 1.2)
    for x in range(14):
        for y in range(12):
            if pen.rng.random() < 0.55:
                a, b = (x + 0.15 + 0.2 * pen.rng.random()) / 14, (y + 0.15 + 0.2 * pen.rng.random()) / 12; pen.box(a, b, a + 0.035, b + 0.04, outline=_mix(CYAN, 0.3 + 0.35 * pen.rng.random()), width=0.8)
    for colour in (AMBER, PINK, GREEN):
        points = [(0.0, pen.rng.random())]
        while points[-1][0] < 1:
            x, y = points[-1]; points += [(x + 0.06 + 0.16 * pen.rng.random(), y)]; points += [(points[-1][0], min(0.97, max(0.03, y + 0.5 * (pen.rng.random() - .5))))]
        pen.line(points, colour, 2.4)
        for point in points[1::3]:
            pen.dot(*point, 0.014, WHITE)
    pen.dot(0.52, 0.48, 0.1, None, _mix(GREEN, 0.8), 1.5); pen.dot(0.52, 0.48, 0.02, GREEN); pen.box(0.02, 0.02, 0.98, 0.98, outline=_mix(CYAN, 0.8), width=1.4)


def body(pen):
    pen.grid(0, 0, 1, 1, 16, 16, _mix(CYAN, 0.07)); pen.pane(0.04, 0.04, 0.44, 0.96); middle = 0.24
    parts = [(0.12, 0.2, 0.045, 0.06)]  # head: top, bottom, half widths
    for top, bottom, wide, low in (*parts, (0.22, 0.48, 0.085, 0.06), (0.48, 0.56, 0.065, 0.075)):
        for index in range(13):
            s = index / 12; y = top + (bottom - top) * s; half = wide + (low - wide) * s
            if top == 0.12: half = 0.045 * math.sqrt(max(0, 1 - (2 * s - 1) ** 2))
            pen.line([(middle - half, y), (middle - half / 2, y + 0.008), (middle, y + 0.011), (middle + half / 2, y + 0.008), (middle + half, y)], _mix(CYAN, 0.85), 0.9)
    for sign in (-1, 1):
        for start, end, wide in (((0.1, 0.24), (0.145, 0.54), 0.02), ((0.04, 0.56), (0.05, 0.92), 0.03)):
            for index in range(17):
                s = index / 16; x = middle + sign * (start[0] + (end[0] - start[0]) * s); y = start[1] + (end[1] - start[1]) * s; half = wide * (1 - 0.5 * s); pen.line([(x - half, y), (x, y + 0.006), (x + half, y)], _mix(CYAN, 0.85), 0.9)
    pen.line([(middle, 0.2), (middle, 0.55)], AMBER, 1.6); pen.dot(middle + 0.025, 0.3, 0.018, PINK); pen.dot(middle, 0.16, 0.014, AMBER)
    pen.pane(0.48, 0.04, 0.96, 0.4, AMBER)
    for index, colour in enumerate((GREEN, CYAN, AMBER, PINK)):
        pen.wave(0.51, 0.09 + index * 0.07, 0.94, 0.17 + index * 0.07, colour, 2 + index)
    pen.pane(0.48, 0.45, 0.96, 0.68, GREEN); pen.wave(0.5, 0.49, 0.94, 0.66, GREEN, 6, 2); pen.pane(0.48, 0.73, 0.96, 0.96); pen.marks(0.51, 0.78, 0.94, 0.94, 6, CYAN)


def menu(pen):
    pen.grid(0, 0, 1, 1, 14, 10, _mix(CYAN, 0.08)); pen.box(0, 0, 1, 0.14, fill=_mix(CYAN, 0.25)); pen.marks(0.05, 0.03, 0.6, 0.12, 1, WHITE, 1); pen.dot(0.92, 0.07, 0.035, None, AMBER, 2)
    for row in range(4):
        y = 0.2 + row * 0.18; colour = (CYAN, AMBER, GREEN, PINK)[row]; pen.box(0.05, y, 0.6, y + 0.14, fill=_mix(colour, 0.12), outline=colour, width=1.6); pen.box(0.08, y + 0.04, 0.12, y + 0.1, fill=colour); pen.marks(0.16, y + 0.03, 0.57, y + 0.12, 2, colour)
    pen.pane(0.65, 0.2, 0.95, 0.88); pen.network(0.68, 0.26, 0.92, 0.6, 14, [CYAN, AMBER]); pen.bars(0.68, 0.66, 0.92, 0.84, 7, [CYAN, AMBER])


def call(pen):
    pen.box(0.02, 0.03, 0.98, 0.97, outline=CYAN, width=1.8); pen.dot(0.24, 0.42, 0.22, _mix(GREEN, 0.15), GREEN, 2.4)
    for index in range(3):
        pen.dot(0.24, 0.42, 0.05 + 0.05 * index, None, GREEN, 1.6)
    pen.marks(0.46, 0.14, 0.93, 0.68, 5, CYAN); pen.box(0.06, 0.78, 0.46, 0.9, outline=AMBER, width=1.6); pen.box(0.54, 0.78, 0.94, 0.9, outline=PINK, width=1.6); pen.marks(0.12, 0.8, 0.4, 0.89, 1, AMBER, 1); pen.marks(0.6, 0.8, 0.88, 0.89, 1, PINK, 1)


def skyline(pen):
    for index in range(40):
        pen.box(0, index / 40, 1, (index + 1) / 40, fill=_mix((86, 30, 92), 0.1 + 0.9 * index / 40, (8, 8, 26)))
    for layer in range(3):
        x = 0.0
        while x < 1:
            wide = 0.04 + 0.08 * pen.rng.random(); top = 0.75 - (0.6 - 0.14 * layer) * pen.rng.random() ** 1.4 - 0.05; tone = ((44, 26, 66), (26, 20, 46), (12, 12, 26))[layer]; pen.box(x, top, x + wide, 1, fill=tone)
            for column in range(5):
                for row in range(int((1 - top) * 34)):
                    if pen.rng.random() < 0.25:
                        a, b = x + wide * (0.1 + 0.17 * column), top + 0.02 + row / 34; pen.box(a, b, a + wide * 0.09, b + 0.012, fill=(AMBER, CYAN, PINK, WHITE)[int(4 * pen.rng.random() ** 2)])
            if pen.rng.random() < 0.3:
                pen.box(x + wide * 0.2, top + 0.06, x + wide * 0.8, top + 0.2, fill=_mix((CYAN, PINK, AMBER)[int(3 * pen.rng.random())], 0.85))
            x += wide + 0.006
    pen.line([(0, 0.72), (0.4, 0.66), (1, 0.7)], WHITE, 2.4); pen.box(0.44, 0.645, 0.6, 0.672, fill=CYAN)


def globe(pen):
    pen.grid(0, 0, 1, 1, 12, 12, _mix(CYAN, 0.08))
    for index in range(-4, 5):
        lean = index / 5; half = math.sqrt(1 - lean * lean) * 0.38; pen.line([(0.5 + half * math.cos(t / 24 * 6.283), 0.5 + lean * 0.38 + 0.06 * half / 0.38 * math.sin(t / 24 * 6.283)) for t in range(25)], _mix(CYAN, 0.7), 1)
        pen.line([(0.5 + lean * 0.38 * math.sin(t / 24 * 3.1416), 0.5 - 0.38 * math.cos(t / 24 * 3.1416)) for t in range(25)], _mix(CYAN, 0.55), 1)
    for _ in range(9):
        a, b = pen.rng.random() * 6.28, 0.34 * pen.rng.random(); pen.dot(0.5 + b * math.cos(a), 0.5 + b * math.sin(a), 0.014, (AMBER, PINK)[int(pen.rng.random() * 2)])
    pen.marks(0.05, 0.9, 0.95, 0.97, 1, AMBER, 1)


def race(pen):
    for index in range(20):
        pen.box(0, index / 40, 1, (index + 1) / 40, fill=_mix(PINK, 0.05 + 0.55 * index / 20, (10, 8, 30)))
    pen.box(0, 0.5, 1, 1, fill=(16, 16, 24))
    for index in range(9):
        x = -0.6 + index * 0.275; pen.line([(0.5, 0.5), (x, 1)], _mix(CYAN, 0.8), 1.4)
    for index in range(7):
        y = 0.5 + 0.5 * (index / 7) ** 2; pen.line([(0, y), (1, y)], _mix(CYAN, 0.5), 1)
    for x, y, big, colour in ((0.38, 0.62, 0.08, AMBER), (0.66, 0.78, 0.15, GREEN)):
        pen.on.polygon([pen.at(x - big * .5, y), pen.at(x - big * .2, y - big * .9), pen.at(x + big * .2, y - big * .9), pen.at(x + big * .5, y)], fill=_mix(colour, 0.75)); pen.dot(x, y, big * 0.3, (6, 6, 8), colour, 1.5); pen.dot(x, y - big * 1.05, big * 0.22, _mix(WHITE, 0.8))
    pen.box(0.04, 0.05, 0.4, 0.1, fill=AMBER); pen.box(0.04, 0.12, 0.28, 0.17, fill=CYAN)


def reader(pen):
    plan(pen); pen.box(0, 0.72, 1, 1, fill=(14, 22, 40))
    pen.on.polygon([pen.at(0.2, 0.86), pen.at(0.3, 0.6), pen.at(0.44, 0.54), pen.at(0.56, 0.54), pen.at(0.7, 0.6), pen.at(0.8, 0.86)], fill=(46, 54, 84)); pen.on.polygon([pen.at(0.44, 0.55), pen.at(0.5, 0.74), pen.at(0.56, 0.55)], fill=WHITE)
    pen.box(0.46, 0.46, 0.54, 0.57, fill=(172, 122, 96)); (cx, cy), r = pen.at(0.5, 0.36), 0.13 * min(pen.size)
    pen.on.ellipse((cx - r * .8, cy - r * 1.1, cx + r * .8, cy + r * 1.1), fill=(190, 138, 110)); pen.on.pieslice((cx - r * .92, cy - r * 1.28, cx + r * .92, cy + r * .9), 180, 360, fill=(34, 24, 30))
    pen.box(0, 0.86, 1, 1, fill=(150, 26, 44)); pen.marks(0.04, 0.88, 0.96, 0.98, 1, WHITE, 1)


def bars(pen):
    for index, colour in enumerate((WHITE, (230, 220, 70), CYAN, GREEN, PINK, (220, 60, 60), (70, 90, 220))):
        pen.box(index / 7, 0, (index + 1) / 7, 0.68, fill=colour)
    for index in range(10):
        pen.box(index / 10, 0.68, (index + 1) / 10, 1, fill=(int(index * 25),) * 3)


FRAMES = (skyline, reader, race, globe, plan, bars, wave, desktop)
KINDS = {'desktop': desktop, 'server': server, 'wave': wave, 'plan': plan, 'body': body, 'menu': menu, 'call': call, 'skyline': skyline, 'globe': globe, 'race': race, 'reader': reader, 'bars': bars}


def draw(kind, width, height, seed=1):
    """A screen of `kind` at width x height, uint8 RGB."""
    require(kind in KINDS, 'A screen is one of ' + ', '.join(sorted(KINDS)))
    pen = _Pen(width, height, seed); KINDS[kind](pen)
    return pen.done(width, height)


def sign(text, width, height, colour, on):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (width * OVER, height * OVER), tuple(on)); pen = ImageDraw.Draw(image); lines = text.split('\n'); size = int(height * OVER * 0.7 / len(lines))
    while size > 4:
        font = ImageFont.load_default(size); wide = max(pen.textbbox((0, 0), line, font=font, stroke_width=size // 24)[2] for line in lines)
        if wide <= width * OVER * 0.9:
            break
        size -= 1
    for index, line in enumerate(lines):
        pen.text((width * OVER / 2, height * OVER * (index + 0.5) / len(lines)), line, font=font, fill=tuple(colour), anchor='mm', stroke_width=size // 24, stroke_fill=tuple(colour))
    return np.asarray(image.resize((width, height), Image.LANCZOS))


def mended(picture, box):
    """The pixel box (left, top, right, bottom) filled from the picture just outside it, each edge fading into the next."""
    left, top, right, bottom = box; high, wide = picture.shape[:2]; picture = picture.astype(float); side = lambda a, limit: min(max(a, 0), limit - 1)
    band = 3; row = lambda y: np.mean([picture[side(y + k, high), left:right] for k in range(band)], axis=0); column = lambda x: np.mean([picture[top:bottom, side(x + k, wide)] for k in range(band)], axis=0)
    above, below, west, east = row(top - band), row(bottom), column(left - band), column(right); rows, columns = bottom - top, right - left
    v, u = ((np.arange(rows) + 0.5) / rows)[:, None, None], ((np.arange(columns) + 0.5) / columns)[None, :, None]
    near = np.stack([np.broadcast_to(one, (rows, columns, 1)) for one in (1 / v, 1 / (1 - v), 1 / u, 1 / (1 - u))]) ** 2
    parts = [np.broadcast_to(above[None], (rows, columns, 3)), np.broadcast_to(below[None], (rows, columns, 3)), np.broadcast_to(west[:, None], (rows, columns, 3)), np.broadcast_to(east[:, None], (rows, columns, 3))]
    return np.uint8(np.clip(sum(n * p for n, p in zip(near, parts)) / near.sum(0), 0, 255) + 0.5)


def laid(picture, parts, name='a picture'):
    """`picture` (uint8 RGB) with the `parts` of a screen list laid on it."""
    picture = np.array(picture[..., :3]); high, wide = picture.shape[:2]
    for part in parts:
        box = part.get('box', ()); require(len(box) == 4 and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1, f'{name}: a part has a box [left, top, right, bottom] in shares of the picture')
        left, top, right, bottom = round(box[0] * wide), round(box[1] * high), round(box[2] * wide), round(box[3] * high); size = (right - left, bottom - top); require(min(size) > 0, f'{name}: a part covers no pixel')
        require(sum(key in part for key in ('draw', 'sign', 'mend')) == 1, f'{name}: a part is one of draw, sign and mend')
        if part.get('mend'):
            made = mended(picture, (left, top, right, bottom))
        else:
            quarter = int(part.get('turn', 0)) % 4; shape = size[::-1] if quarter % 2 else size
            made = draw(part['draw'], *shape, int(part.get('seed', 1))) if 'draw' in part else sign(part['sign']['text'], *shape, part['sign']['colour'], part['sign']['on'])
            made = np.rot90(made, quarter)
        picture[top:bottom, left:right] = np.uint8(made * (1 - float(part.get('dim', 0))) + 0.5)
    return picture


def build(spec, repo, folder, *, enlarged=None, redrawn=None, only=None, stock=None):
    """Every texture of the screen list `spec` made into `folder` as <name>.png with the record `material.build` checks.
    It starts from the picture `redraw` left in `redrawn` where the texture says `over`: 'redrawn', else from the
    enlarged one where it is `doubled`, else from the picture as it is. Returns {name: parts laid}."""
    from PIL import Image
    textures = spec['textures']; chosen = sorted(textures) if only is None else list(only); folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    for name in chosen:
        how = textures[name]; require(how.get('screen'), f'{name} has no parts (`screen`)')
        old = np.ascontiguousarray(np.asarray(material.current(repo, name, stock=stock, **material.of_spec(spec)))[..., :3])
        base = enlarge.picture_of(redrawn, name, 'redrawn', 'redraw') if how.get('over') == 'redrawn' else enlarge.picture_of(enlarged, name) if how.get('doubled') else old
        whole = np.asarray(Image.fromarray(base).resize(tuple(how['size']), Image.LANCZOS)); Image.fromarray(laid(whole, how['screen'], name)).save(folder / f'{name}.png')
        (folder / f'{name}.json').write_text(json.dumps({'kind': 'tilekit-screen', 'texture': name, 'source': hashlib.sha256(repr(old.shape).encode() + old.tobytes()).hexdigest(), 'screen': how['screen']}, indent=1) + '\n', encoding='utf-8')
        told[name] = len(how['screen'])
    return told
