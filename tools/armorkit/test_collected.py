"""Every test written in the kit's test files is one the runner finds."""
import re
import unittest
from pathlib import Path

MAIN = "if __name__ == '__main__':"


class CollectedTests(unittest.TestCase):
    def test_nothing_follows_a_test_files_main_block(self):
        # a test appended below the block was read as a function inside it, and never ran: a bake then failed
        # on the code it was written to check (2026-11-15)
        for path in sorted(Path(__file__).parent.glob('test_*.py')):
            text = path.read_text(encoding='utf-8')
            found = re.search('^' + re.escape(MAIN), text, re.M)
            if found is None:
                continue
            after = text[found.end():]
            self.assertIsNone(re.search(r'^\s*(def|class) ', after, re.M), f'{path.name} defines something below its main block')


if __name__ == '__main__':
    unittest.main()
