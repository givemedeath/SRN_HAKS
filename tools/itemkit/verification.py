"""Fresh, operation-local byte verification; never a persistent metadata cache."""
from pathlib import Path
from tools.headkit.common import sha, require


class VerificationPass:
    def __init__(self):
        self.hashes = {}
        self.expected = {}
        self.results = {}
        self.receipts = {}
        self.code_version = None
        self.bytes_hashed = 0

    def verify(self, rows):
        for row in rows:
            path = str(Path(row['path']).resolve())
            expected = row['sha256']
            require(path not in self.expected or self.expected[path] == expected,
                    'Conflicting file pins: '+path)
            self.expected[path] = expected
            if path not in self.hashes:
                self.hashes[path] = sha(path)
                self.bytes_hashed += Path(path).stat().st_size
            require(self.hashes[path] == expected, 'Stale file pin: '+path)
