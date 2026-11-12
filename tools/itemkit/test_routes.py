"""The family table is the single source of each route's shape."""
import unittest
from .contracts import PARTS
from .firearms import SLOTS
from .parts import active_parts
from .routes import (GRIP_BOUND_FAMILIES, HAFTED_FAMILIES, PACKAGED_FIREARMS, RIGGED_NATIVE_FAMILIES, ROUTES, TWO_HAND_FAMILIES,
                     WHOLE_NATIVE_FAMILIES, needs_grip_standard)


class RouteTableTests(unittest.TestCase):
    def test_derived_family_lists_match_the_qualified_routes(self):
        self.assertEqual(set(WHOLE_NATIVE_FAMILIES),{'firearm-sling','firearm-crossbow','crossbow'})
        self.assertEqual(set(PACKAGED_FIREARMS),{'firearm-sling','firearm-crossbow'})
        self.assertEqual(set(RIGGED_NATIVE_FAMILIES),{'bow','whip'})
        self.assertEqual(set(HAFTED_FAMILIES),{'club','handaxe','battleaxe','greataxe','halberd','scythe','spear'})
        self.assertEqual(set(GRIP_BOUND_FAMILIES),{'shortsword','dagger','longsword','greatsword',*HAFTED_FAMILIES,*WHOLE_NATIVE_FAMILIES})
        self.assertEqual(set(TWO_HAND_FAMILIES),{'greatsword','greataxe','halberd','scythe'})

    def test_hafted_carriers_are_the_installed_base_items(self):
        # baseitems.2da rows: Club 28 WBlCl, Handaxe 38 WAxHn, Battleaxe 2 WAxBt, Greataxe 18 WAxGr, Halberd 10 WPlHb,
        # Scythe 55 WPlSc, Shortspear 58 WPlSs. Two-handers are the rows without the left-hand slot (0x1C010).
        rows = {'club': (28, 'wblcl'), 'handaxe': (38, 'waxhn'), 'battleaxe': (2, 'waxbt'), 'greataxe': (18, 'waxgr'),
                'halberd': (10, 'wplhb'), 'scythe': (55, 'wplsc'), 'spear': (58, 'wplss')}
        for name, (base, item_class) in rows.items():
            with self.subTest(family=name):
                carrier = ROUTES[name].carrier; self.assertEqual((carrier.base_item, carrier.item_class), (base, item_class))
                self.assertEqual(ROUTES[name].carry == 'shoulder', ROUTES[name].hold == 'two')

    def test_two_hand_fit_needs_the_grip_standard_on_every_family(self):
        self.assertTrue(needs_grip_standard('dagger',{}))
        self.assertFalse(needs_grip_standard('staff',{}))
        self.assertTrue(needs_grip_standard('staff',{'sizingAuthority':'midpoint-depth-two-hand'}))

    def test_every_route_is_internally_consistent(self):
        for name,route in ROUTES.items():
            with self.subTest(family=name):
                self.assertIn(route.adapter,('composite','rigged','whole-skinned','whole-rigid','shield','none'))
                self.assertEqual(route.parts is None,route.adapter=='whole-rigid')
                self.assertEqual(route.hidden_slots,route.adapter in ('rigged','whole-skinned','whole-rigid'))
                self.assertEqual(route.runtime_size==1024,name in WHOLE_NATIVE_FAMILIES)
                if route.adapter=='composite':self.assertEqual(route.parts,PARTS)
                if route.carrier:self.assertEqual(route.carrier.canvas is None or route.carrier.icon is not None,True)

    def test_declared_firearm_subtype_picks_the_slot(self):
        for subtype,slot in SLOTS.items():
            self.assertEqual(active_parts({'family':'firearm-sling','firearm':{'subtype':subtype}}),(slot,))
        self.assertEqual(active_parts({'family':'shield'}),PARTS)
        self.assertEqual(active_parts({'family':'shield','nativePackaging':'enabled','native':{'kind':'shield-whole-v1'}}),('whole',))


if __name__ == '__main__':
    unittest.main()
