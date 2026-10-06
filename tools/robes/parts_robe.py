"""parts_robe.2da columns, reader and position-true writer shared by the robe tools."""
from pathlib import Path

from robe_common import require

HIDE = ("HIDEFOOTR", "HIDEFOOTL", "HIDESHINR", "HIDESHINL", "HIDELEGR", "HIDELEGL", "HIDEPELVIS", "HIDECHEST",
        "HIDEBELT", "HIDENECK", "HIDEFORER", "HIDEFOREL", "HIDEBICEPR", "HIDEBICEPL", "HIDESHOR", "HIDESHOL",
        "HIDEHANDR", "HIDEHANDL", "HIDEHEAD")


def write_2da(path, columns, rows):
    widths = [max(len(c), 4) + 2 for c in columns]
    lines = ["2DA V2.0", "", "    " + "".join(c.ljust(w) for c, w in zip(columns, widths))]
    # The engine indexes 2DA rows by position, not label: gaps are padded with empty rows so labels stay true.
    for index in range(max(rows) + 1):
        values = [str(rows.get(index, {}).get(c, "****")) for c in columns]
        lines.append(str(index).ljust(4) + "".join(v.ljust(w) for v, w in zip(values, widths)))
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")


def read_2da(path):
    lines = [line for line in Path(path).read_text(encoding="cp1252").splitlines() if line.strip()]
    require(lines[0].startswith("2DA"), "2DA header required")
    columns = lines[1].split()
    return columns, {int(v[0]): dict(zip(columns, v[1:])) for v in (line.split() for line in lines[2:])}
