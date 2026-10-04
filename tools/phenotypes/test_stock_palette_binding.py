"""Actual stock model bitmap aliases must survive the private comparator."""
from pathlib import Path
import tempfile
import unittest
from stock_body_control import stock_palette


class StockPaletteBindingTests(unittest.TestCase):
    def test_hand003_and_opposite_palette_are_resolved_from_bitmap(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)/'stock';(base/'raw').mkdir(parents=True)
            extra=Path(temporary)/'supplement';extra.mkdir()
            (base/'raw/pmh0_handl001.plt').write_bytes(b'wrong-style')
            (base/'raw/pmh0_bicepl001.plt').write_bytes(b'actual-left-palette')
            (base/'raw/pmh0_bicepr001.plt').write_bytes(b'unreferenced-right-palette')
            (extra/'pmh0_handl003.plt').write_bytes(b'actual-gripping-palette')
            bitmap,path=stock_palette(' bitmap pmh0_handl003\n',base,extra)
            self.assertEqual(bitmap,'pmh0_handl003');self.assertEqual(path.read_bytes(),b'actual-gripping-palette')
            _,path=stock_palette(' bitmap pmh0_bicepl001\n',base,extra)
            self.assertEqual(path.read_bytes(),b'actual-left-palette')

    def test_missing_multi_bitmap_and_conflicting_banks_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)/'stock';(base/'raw').mkdir(parents=True)
            extra=Path(temporary)/'supplement';extra.mkdir()
            for text in ['bitmap pmh0_handl003\n','bitmap one\nbitmap two\n','bitmap NULL\n']:
                with self.assertRaises(RuntimeError):stock_palette(text,base,extra)
            (base/'raw/pmh0_handl003.plt').write_bytes(b'first')
            (extra/'pmh0_handl003.plt').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'Ambiguous'):
                stock_palette('bitmap pmh0_handl003\n',base,extra)


if __name__=='__main__':unittest.main()
