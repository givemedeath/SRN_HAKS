"""Every tileset with a walkmesh baseline (docs/tilesets/<tileset>/walkmesh.json) still has the walkmeshes it records.
A restyle changes how its tiles look, never where a creature walks: areas already built stand on these walkmeshes."""
import json
import unittest
from pathlib import Path

from tools.tilekit import inventory

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_dgt04', 'srn_t_udp1', 'srn_t_fcx01', 'srn_t_common', 'srn_2da')  # what the baselines read: named so the test selector runs this when one changes


class Baselines(unittest.TestCase):
    def test_every_walkmesh_stands_as_its_baseline_records_it(self):
        found = sorted((REPO / 'docs' / 'tilesets').glob('*/walkmesh.json'))
        self.assertTrue(found, 'no walkmesh baseline found')
        for path in found:
            baseline = json.loads(path.read_text(encoding='utf-8-sig'))
            with self.subTest(tileset=baseline['tileset']):
                self.assertIn(f"srn_t_{baseline['tileset']}", PACKS)  # a new baseline names its pack above
                _, now = inventory.inventory(REPO, baseline['tileset'], walkmesh_only=True)
                self.assertEqual(inventory.moved(baseline, now), [])


if __name__ == '__main__':
    unittest.main()
