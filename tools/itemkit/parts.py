"""Visible processing parts, with explicit inactive native placeholder accounting."""
from tools.headkit.common import require
from .firearms import SLOTS
from .geometry import check_budgets

FIREARM_VIEWS = ('left','right','muzzle','rear','top','underside','grip','oblique')


def firearm_views(settings):
    import numpy as np
    require(isinstance(settings,dict) and set(settings)==set(FIREARM_VIEWS), 'Eight explicit firearm views required')
    for row in settings.values():
        require(set(row)=={'direction','target','up','scale'}, 'Explicit view direction, target, up and scale required')
        for key in ('direction','target','up'):
            vector=np.asarray(row[key],float)
            require(vector.shape==(3,) and np.isfinite(vector).all(), 'Finite camera vectors required')
        direction=np.asarray(row['direction'],float);up=np.asarray(row['up'],float)
        require(np.linalg.norm(direction)>1e-8 and np.linalg.norm(up)>1e-8
                and np.linalg.norm(np.cross(direction,up))/(np.linalg.norm(direction)*np.linalg.norm(up))>1e-4,
                'Nondegenerate camera frame required')
        require(type(row['scale']) in (float,int) and np.isfinite(row['scale']) and .01<=row['scale']<=3,
                'Bounded relative camera scale required')
    return {name:settings[name] for name in FIREARM_VIEWS}


def active_parts(profile):
    if profile['family'] != 'firearm-sling': return ('b', 'm', 't')
    subtype = profile.get('firearm', {}).get('subtype')
    require(subtype in SLOTS, 'Declare the whole-firearm native slot before processing')
    return (SLOTS[subtype],)


def assembly_budget(profile, counts, kind):
    active = active_parts(profile)
    require(set(counts) == set(active), 'Count every active processing part exactly once')
    full = dict(counts)
    if profile['family'] == 'firearm-sling':
        require(kind in ('visible', 'shadow'), 'Known budget kind required')
        for part in set(('b','m','t'))-set(active):
            require(profile['budgets']['parts'][part] == {'visible':4, 'shadow':0},
                    'Inactive slots must be tiny hidden placeholders')
            full[part] = 4 if kind == 'visible' else 0
    return check_budgets(full, profile['budgets'], kind)
