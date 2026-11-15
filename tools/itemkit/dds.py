"""BioWare DDS and TGA headers, read without an image library: the checks a package's DDS twins must pass.

A BioWare DDS (NWN Crunch `-fileformat nwn`, the base game's own icons) is a 20-byte header (width, height, channels,
top-level size, alpha mean) followed by DXT blocks: DXT1 (8 bytes a block) for three channels, DXT5 (16) for four.
"""
import struct


def tga_size(data):
    """(width, height) of a TGA file's header."""
    if len(data) < 18: raise ValueError('Not a TGA file')
    return struct.unpack_from('<2H', data, 12)


def bioware_dds(data):
    """(width, height, channels, mip levels) of a BioWare DDS, after checking its header and payload length."""
    if len(data) < 20 or data[:4] == b'DDS ': raise ValueError('Not a BioWare DDS (too short, or a standard DDS)')
    width, height, channels, top = struct.unpack_from('<4I', data)
    if channels not in (3, 4) or not width or not height: raise ValueError(f'Unsupported BioWare DDS header {width}x{height}x{channels}')
    block = 8 if channels == 3 else 16
    total, levels, x, y = 0, 0, width, height
    while True:
        total += max(1, (x + 3)//4) * max(1, (y + 3)//4) * block; levels += 1
        if total == len(data) - 20: break
        if total > len(data) - 20 or (x, y) == (1, 1): raise ValueError('BioWare DDS payload is not a whole mip chain')
        x, y = max(1, x//2), max(1, y//2)
    if top != max(1, (width + 3)//4) * max(1, (height + 3)//4) * block: raise ValueError('BioWare DDS top-level size differs')
    return width, height, channels, levels


def twin_problem(dds, tga):
    """Why a DDS (bytes) is not a sound twin of its TGA (bytes), or None."""
    try: width, height, _, _ = bioware_dds(dds); size = tga_size(tga)
    except ValueError as error: return str(error)
    return None if (width, height) == size else f'{width}x{height} differs from its TGA {size[0]}x{size[1]}'
