"""Visible processing parts, with explicit inactive native placeholder accounting."""
from tools.headkit.common import require
from .firearms import SLOTS
from .geometry import check_budgets
from .routes import GRIP_BOUND_FAMILIES, MULTIPART, RIGGED_NATIVE_FAMILIES, ROUTES, WHOLE_NATIVE_FAMILIES, whole_shield

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
    route = ROUTES[profile['family']]
    # A shield without the whole-model contract stays a blocked multipart design.
    if profile['family'] == 'shield' and not whole_shield(profile): return MULTIPART
    if route.parts is not None: return route.parts
    subtype = profile.get('firearm', {}).get('subtype')
    require(subtype in SLOTS, 'Declare the whole-firearm native slot before processing')
    return (SLOTS[subtype],)


def active_icon_dimensions(profile):
    dimensions=profile['native'].get('iconDimensions')
    active=active_parts(profile)
    require(isinstance(dimensions,dict), 'Measure active-part inventory icon dimensions')
    if profile['family'] in RIGGED_NATIVE_FAMILIES:
        require(set(dimensions)=={'b','m','t'}, 'Measure all rigged donor inventory icon dimensions')
        dimensions={part:dimensions[part] for part in active}
    require(set(dimensions)==set(active), 'Measure active-part inventory icon dimensions')
    return dimensions


def fitting_parts(profile, joins):
    """Whole meshes keep both ends; only multipart melee uses cut planes."""
    import math
    active=active_parts(profile)
    if len(active)==1:
        require(not joins, 'A single-part weapon must not inherit melee part cuts')
    else:
        require(len(joins)==2 and all(math.isfinite(y) for y in joins) and joins[0]<joins[1],
                'Two ordered natural part cuts required')
    return active


def grip_render_part(profile):
    active=active_parts(profile)
    part=profile['native'].get('gripPart',active[0] if len(active)==1 else 'm')
    require(part in active, 'Grip close-up must use an active part')
    return part


def assembly_budget(profile, counts, kind):
    active = active_parts(profile)
    require(set(counts) == set(active), 'Count every active processing part exactly once')
    full = dict(counts)
    if profile['family'] in WHOLE_NATIVE_FAMILIES + RIGGED_NATIVE_FAMILIES:
        require(kind in ('visible', 'shadow'), 'Known budget kind required')
        for part in set(('b','m','t'))-set(active):
            require(profile['budgets']['parts'][part] == {'visible':4, 'shadow':0},
                    'Inactive slots must be tiny hidden placeholders')
            full[part] = 4 if kind == 'visible' else 0
    return check_budgets(full, profile['budgets'], kind)


def side_grip_budgets(profile, manifest):
    """The family with a side grip's reviewed re-split of its part budgets (`processing.partBudgets`).

    A side grip's parts are slices across the grip axis, so the long body lies in all three and most of it in the grip
    part: the wave-5 Katar has 60% of its surface in `m`, which the dagger family gives 19% of the budget, and each
    join's protected seam alone filled an end part's 900 triangles. The visible and shadow totals stay the family's
    own; only their split across the active parts changes."""
    split = (manifest.get('processing') or {}).get('partBudgets')
    if split is None: return profile
    require((manifest.get('fit') or {}).get('sideGrip') is True, 'Part budgets are re-split only for a side grip')
    budgets = profile['budgets']; parts = budgets['parts']
    require(isinstance(split, dict) and set(split) == set(parts) and set(parts) == set(active_parts(profile)),
            'Re-split every active part, and only those')
    require(all(isinstance(row, dict) and set(row) == {'visible', 'shadow'} for row in split.values()),
            'Part budgets are visible and shadow only')
    for kind in ('visible', 'shadow'):
        require(all(type(row[kind]) is int and row[kind] >= 4 for row in split.values()), f'Each part needs a {kind} budget of 4 or more')
        require(sum(row[kind] for row in split.values()) <= budgets[kind], f'Re-split {kind} budgets exceed the family total')
    return {**profile, 'budgets': {**budgets, 'parts': {p: dict(split[p]) for p in parts}}}
