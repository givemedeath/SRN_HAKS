"""Tile kit: what a tileset's own tiles draw, for restyling them in place. Nothing is read on import."""


def require(condition, message):
    if not condition:
        raise ValueError(message)
