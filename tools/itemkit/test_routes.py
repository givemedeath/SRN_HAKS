"""The family table is the single source of each route's shape."""
import unittest
from .contracts import PARTS
from .firearms import SLOTS
from .parts import active_parts
from .routes import GRIP_BOUND_FAMILIES, PACKAGED_FIREARMS, RIGGED_NATIVE_FAMILIES, ROUTES, WHOLE_NATIVE_FAMILIES, needs_grip_standard


class RouteTableTests(unittest.TestCase):
    def test_derived_family_lists_match_the_qualified_routes(self):
        self.assertEqual(set(WHOLE_NATIVE_FAMILIES),{'firearm-sling','firearm-crossbow','crossbow'})
        self.assertEqual(set(PACKAGED_FIREARMS),{'firearm-sling','firearm-crossbow'})
        self.assertEqual(set(RIGGED_NATIVE_FAMILIES),{'bow','whip'})
        self.assertEqual(set(GRIP_BOUND_FAMILIES),{'shortsword','dagger','longsword','greatsword',*WHOLE_NATIVE_FAMILIES})

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
