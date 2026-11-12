"""One record per item family. Adding a family starts here, not in the stages."""
from typing import NamedTuple

MULTIPART = ('b', 'm', 't')


class Carrier(NamedTuple):
    base_item: int
    item_class: str
    label: str
    icon: list = None  # Logical footprint, checked against its stock multipart icons.
    canvas: list = None  # Stock power-of-two canvas when it differs from the footprint.
    wield: str = None


class Route(NamedTuple):
    adapter: str  # composite, rigged, whole-skinned, whole-rigid, shield or none.
    parts: tuple = MULTIPART  # None lets the declared firearm subtype pick the slot.
    carrier: Carrier = None
    grip_bound: bool = False
    hidden_slots: bool = False  # Inactive parts ship as tiny hidden placeholders.
    longarm: bool = False
    runtime_size: int = None
    subtypes: tuple = ()  # Firearm subtypes allowed; None allows any qualified slot.
    hold: str = 'one'  # 'two' for a weapon held in both hands: sized uniformly, never by the one-hand usable length.
    carry: str = 'hip'  # Scripted fixture framing: 'shoulder' for a long two-hander resting on the right shoulder.
    shape: str = 'bladed'  # 'hafted' for a club, axe or polearm: a long handle with the mass at one end and no guard.


ROUTES = {
    'shortsword': Route('composite', carrier=Carrier(0, 'wswss', 'Shortsword'), grip_bound=True),
    'dagger': Route('composite', carrier=Carrier(22, 'wswdg', 'Dagger'), grip_bound=True),
    'longsword': Route('composite', carrier=Carrier(1, 'wswls', 'Longsword'), grip_bound=True),
    'greatsword': Route('composite', carrier=Carrier(13, 'wswgs', 'Greatsword', [64,160], [64,256]), grip_bound=True,
                        hold='two', carry='shoulder'),
    # Hafted families (user, 2026-11-11): a round handle with the head at one end. One-handers keep the handle round
    # (usable-length-round); two-handers are sized uniformly from the stock carrier like the greatsword.
    'club': Route('composite', carrier=Carrier(28, 'wblcl', 'Club'), grip_bound=True, shape='hafted'),
    'handaxe': Route('composite', carrier=Carrier(38, 'waxhn', 'Handaxe'), grip_bound=True, shape='hafted'),
    'battleaxe': Route('composite', carrier=Carrier(2, 'waxbt', 'Battleaxe'), grip_bound=True, shape='hafted'),
    'greataxe': Route('composite', carrier=Carrier(18, 'waxgr', 'Greataxe'), grip_bound=True, shape='hafted',
                      hold='two', carry='shoulder'),
    'halberd': Route('composite', carrier=Carrier(10, 'wplhb', 'Halberd'), grip_bound=True, shape='hafted',
                     hold='two', carry='shoulder'),
    'scythe': Route('composite', carrier=Carrier(55, 'wplsc', 'Scythe'), grip_bound=True, shape='hafted',
                    hold='two', carry='shoulder'),
    'spear': Route('composite', carrier=Carrier(58, 'wplss', 'Shortspear'), grip_bound=True, shape='hafted'),
    'staff': Route('composite', carrier=Carrier(50, 'wdbqs', 'Staff', [32,128])),
    'throwing-knife': Route('composite', carrier=Carrier(63, 'wthax', 'thrown', [32,64], wield='11')),
    'bow': Route('rigged', ('m',), Carrier(8, 'wbwln', 'rigged', [64,128], wield='5'), hidden_slots=True),
    'whip': Route('rigged', ('m',), Carrier(111, 'wwhip', 'rigged', [64,64], wield='****'), hidden_slots=True),
    'crossbow': Route('whole-skinned', ('t',), grip_bound=True, hidden_slots=True, longarm=True, runtime_size=1024),
    'firearm-crossbow': Route('whole-rigid', None, grip_bound=True, hidden_slots=True, longarm=True, runtime_size=1024,
                              subtypes=('rifle',)),
    'firearm-sling': Route('whole-rigid', None, grip_bound=True, hidden_slots=True, runtime_size=1024, subtypes=None),
    'shield': Route('shield', ('whole',)),
    'catalog-object': Route('none', ('whole',)),
}
WHOLE_NATIVE_FAMILIES = tuple(name for name, route in ROUTES.items() if route.adapter.startswith('whole-'))
PACKAGED_FIREARMS = tuple(name for name, route in ROUTES.items() if route.adapter == 'whole-rigid')
RIGGED_NATIVE_FAMILIES = tuple(name for name, route in ROUTES.items() if route.adapter == 'rigged')
GRIP_BOUND_FAMILIES = tuple(name for name, route in ROUTES.items() if route.grip_bound)
TWO_HAND_FAMILIES = tuple(name for name, route in ROUTES.items() if route.hold == 'two' and route.grip_bound)
HAFTED_FAMILIES = tuple(name for name, route in ROUTES.items() if route.shape == 'hafted')


def needs_grip_standard(family, fit):
    """Grip-bound families and any midpoint-depth two-hand fit size from the approved grip."""
    return family in GRIP_BOUND_FAMILIES or fit.get('sizingAuthority') == 'midpoint-depth-two-hand'


def whole_shield(data):
    return (data.get('family') == 'shield' and data.get('nativePackaging') == 'enabled'
            and data.get('native', {}).get('kind') == 'shield-whole-v1')
