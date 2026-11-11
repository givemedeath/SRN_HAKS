"""Environment kit: buildings and props for the FRFZ areas. Nothing is generated on import."""


def require(condition, message):
    if not condition:
        raise ValueError(message)
