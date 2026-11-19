"""The SRN dynamic skies: panoramas, skyboxes.2da rows and each phase's material parameters.

Parameters (srn_skybox/srn_sky_math.shd documents each):
  SkyPhase 0 dawn, 1 day, 2 dusk, 3 night.
  Colours are linear-ish display RGB 0..1; alpha slots carry the extra value named in the shader.
Azimuths are the sky sphere's: 0 is the area's east (+x), 90 north (+y), 180 west, 270 south.
"""

# A panorama: three views that read left to right as a viewer turns clockwise, each
# 1248x832 with a flat chroma-key sky, and the three redrawn joins between them (view 0-1, 1-2, 2-0); see
# panorama.assemble. `below` is the degrees of the strip's bottom under the horizon, `stretch` the vertical scale of
# square texels (below 1 squats the land into a lower band).
PANORAMAS = {
    # Denver grows from the Codex west view: four redrawn extensions to the right (north, then east, then south) and a
    # closing join back to the start, so every piece keeps the west view's scale and horizon (panorama.chain)
    'den': {
        'chain': ['denver/view_w.png', 'denver/ext_1.png', 'denver/ext_2.png', 'denver/ext_3.png', 'denver/ext_4.png'],
        'close': 'denver/join_close.png',
        'key': 'green', 'below': 2.0, 'stretch': 0.6, 'city_from': 0.42,  # the Front Range fills the strip's upper part
    },
    'stm': {
        'views': ['storm/view_a.png', 'storm/view_b.png', 'storm/view_c.png'],
        'joins': ['storm/join_ab.png', 'storm/join_bc.png', 'storm/join_ca.png'],
        'key': 'magenta', 'below': 2.0, 'stretch': 0.42,
    },
    'pk': {
        'views': ['peaks/view_a.png', 'peaks/view_b.png', 'peaks/view_c.png'],
        'joins': ['peaks/join_ab.png', 'peaks/join_bc.png', 'peaks/join_ca.png'],
        'key': 'magenta', 'below': 2.0, 'stretch': 0.7,
    },
}

DEN_DAWN = {
    'SkyPhase': 0,
    'SkyZenith': (0.16, 0.18, 0.40, 0.8), 'SkyHorizon': (0.98, 0.58, 0.46, 5.0),
    'SkyCloud': (0.62, 0.42, 0.58, 1), 'SkyLand': (1.05, 0.88, 0.92, 0.15),
    'SkySun': (8.0, 3.0, 1.6, 1.0), 'SkySunColor': (1.0, 0.62, 0.36, 0.9),
    'SkyMotion': (2.4, 0.52, 0.0, 0.0), 'SkyNight': (0.0, 0.0, 0.0, 0.55),
    'SkyExtra': (0.0, 0.6, 0.15, 0.0), 'SkyGlow': (1.0, 0.55, 0.65, 1), 'SkyBand': (0.0, 0.0, 0.10, 0.0),
}
DEN_DAY = {
    'SkyPhase': 1,
    'SkyZenith': (0.20, 0.40, 0.78, 0.5), 'SkyHorizon': (0.72, 0.80, 0.92, 4.0),
    'SkyCloud': (0.96, 0.96, 0.98, 1), 'SkyLand': (1.35, 1.25, 1.15, 0.45),
    'SkySun': (200.0, 62.0, 1.4, 0.45), 'SkySunColor': (1.0, 0.95, 0.85, 0.3),
    'SkyMotion': (2.4, 0.46, 0.0, 0.0), 'SkyNight': (0.0, 0.0, 0.0, 0.0),
    'SkyExtra': (0.0, 0.0, 0.0, 0.0), 'SkyGlow': (0.0, 0.0, 0.0, 1), 'SkyBand': (0.0, 0.0, 0.14, 0.9),
}
DEN_DUSK = {
    'SkyPhase': 2,
    'SkyZenith': (0.16, 0.07, 0.30, 0.85), 'SkyHorizon': (0.96, 0.34, 0.46, 5.0),
    'SkyCloud': (0.42, 0.18, 0.44, 1), 'SkyLand': (1.08, 0.86, 1.0, 0.0),
    'SkySun': (172.0, 2.0, 1.8, 1.2), 'SkySunColor': (1.0, 0.42, 0.50, 1.1),
    'SkyMotion': (2.4, 0.64, 0.0, 0.0), 'SkyNight': (0.25, 0.0, 0.0, 0.8),
    'SkyExtra': (0.0, 0.9, 0.45, 0.0), 'SkyGlow': (1.0, 0.45, 0.70, 1), 'SkyBand': (0.0, 0.0, 0.06, 0.0),
}
DEN_NIGHT = {
    'SkyPhase': 3,
    'SkyZenith': (0.015, 0.02, 0.06, 0.0), 'SkyHorizon': (0.12, 0.06, 0.20, 4.0),
    'SkyCloud': (0.13, 0.09, 0.18, 1), 'SkyLand': (0.80, 0.80, 0.90, 0.0),
    'SkySun': (172.0, -30.0, 1.0, 0.0), 'SkySunColor': (0.0, 0.0, 0.0, 0.0),
    'SkyMotion': (2.4, 0.48, 0.0, 0.0), 'SkyNight': (1.0, 1.0, 0.0, 1.3),
    # searchlights sweep the Denver night too (user, 2026-11-19)
    'SkyExtra': (0.8, 1.0, 0.75, 0.0), 'SkyGlow': (1.0, 0.42, 0.72, 1), 'SkyBand': (0.0, 0.0, 0.05, 0.0),
}
STORM = {
    'SkyPhase': 3,
    'SkyZenith': (0.01, 0.02, 0.025, 0.0), 'SkyHorizon': (0.10, 0.14, 0.12, 3.0),
    'SkyCloud': (0.21, 0.26, 0.23, 1), 'SkyLand': (0.80, 0.90, 0.85, 0.10),
    'SkySun': (172.0, -30.0, 1.0, 0.0), 'SkySunColor': (0.0, 0.0, 0.0, 0.0),
    'SkyMotion': (5.0, 0.55, 0.75, 1.0), 'SkyNight': (0.0, 0.0, 0.0, 1.2),
    'SkyExtra': (0.9, 1.0, 0.9, 0.55), 'SkyGlow': (0.75, 0.85, 0.35, 1), 'SkyBand': (0.0, 0.0, 0.06, 0.0),
}
# The Awakened wilderness: neutral daylight art, tinted per phase; no city, so no window light, beacons or city glow.
PK_DAWN = dict(DEN_DAWN, SkyLand=(1.0, 0.82, 0.78, 0.0), SkyNight=(0.0, 0.0, 0.0, 0.0), SkyExtra=(0.0, 0.0, 0.0, 0.0),
               SkyGlow=(0.0, 0.0, 0.0, 1), SkyBand=(0.0, 0.0, 0.14, 0.0))
PK_DAY = dict(DEN_DAY, SkyLand=(1.0, 1.0, 1.0, 0.0), SkyBand=(0.0, 0.0, 0.10, 0.0))
PK_DUSK = dict(DEN_DUSK, SkyLand=(0.86, 0.62, 0.72, 0.0), SkyNight=(0.25, 0.0, 0.0, 0.0), SkyExtra=(0.0, 0.0, 0.0, 0.0),
               SkyGlow=(0.0, 0.0, 0.0, 1), SkyBand=(0.0, 0.0, 0.10, 0.0))
PK_NIGHT = dict(DEN_NIGHT, SkyLand=(0.22, 0.28, 0.42, 0.2), SkyCloud=(0.08, 0.09, 0.14, 1), SkyMotion=(2.4, 0.30, 0.0, 0.0),
                SkyNight=(1.3, 1.0, 1.0, 0.0), SkyExtra=(0.0, 0.0, 0.0, 0.0), SkyGlow=(0.0, 0.0, 0.0, 1),
                SkyHorizon=(0.05, 0.07, 0.14, 4.0), SkyBand=(0.0, 0.0, 0.08, 0.0))

# skyboxes.2da rows: id -> (label, cyclical, panorama, {model suffix: phase parameters}, (dawn, day, dusk, night) suffixes)
SKIES = {
    16: ('SRN_Denver_Dynamic', 1, 'den', {'da': DEN_DAWN, 'd': DEN_DAY, 'du': DEN_DUSK, 'n': DEN_NIGHT, 'st': STORM}, ('da', 'd', 'du', 'n')),
    17: ('SRN_Sprawl_AcidStorm', 0, 'stm', {'st': STORM}, ('st', 'st', 'st', 'st')),
    18: ('SRN_Denver_Dusk_Fixed', 0, 'den', {}, ('du', 'du', 'du', 'du')),
    19: ('SRN_Denver_Night_Fixed', 0, 'den', {}, ('n', 'n', 'n', 'n')),
    20: ('SRN_Awakened_Peaks', 1, 'pk', {'da': PK_DAWN, 'd': PK_DAY, 'du': PK_DUSK, 'n': PK_NIGHT}, ('da', 'd', 'du', 'n')),
    21: ('SRN_Awakened_Aurora', 0, 'pk', {}, ('n', 'n', 'n', 'n')),
    22: ('SRN_Denver_AcidStorm', 0, 'den', {}, ('st', 'st', 'st', 'st')),  # Denver's skyline under the acid storm
}


def sources(panorama):
    """The art files a panorama is built from."""
    spec = PANORAMAS[panorama]
    if 'chain' in spec:
        return spec['chain'] + [spec['close']]
    return spec['views'] + spec['joins']


def model_name(panorama, suffix):
    """srn_sky<panorama>_<suffix>: model, material and fallback picture share it (16 characters at most)."""
    name = f'srn_sky{panorama}_{suffix}'
    assert len(name) <= 16, name
    return name


def texture_names(panorama):
    """The two land halves and their light masks."""
    return [f'srn_sky{panorama}_{part}' for part in ('pa', 'pb', 'ma', 'mb')]


def materials():
    """{model name: (panorama, parameters)} of every model the rows name."""
    out = {}
    for label, cyclical, panorama, phases, columns in SKIES.values():
        for suffix, parameters in phases.items():
            out[model_name(panorama, suffix)] = (panorama, parameters)
    for label, cyclical, panorama, phases, columns in SKIES.values():
        for suffix in columns:
            if model_name(panorama, suffix) not in out:
                raise ValueError(f'{label}: no phase {suffix} for {panorama}')
    return out
