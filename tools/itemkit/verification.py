"""Fresh, operation-local byte verification; never a persistent metadata cache."""
from pathlib import Path
from tools.headkit.common import sha, require


class VerificationPass:
    def __init__(self):
        self.hashes = {}
        self.expected = {}
        self.resolved = {}
        self.results = {}
        self.receipts = {}
        self.code_version = None
        self.bytes_hashed = 0

    def verify(self, rows):
        for row in rows:
            path = self.resolved.get(row['path'])
            if path is None: path = self.resolved[row['path']] = str(Path(row['path']).resolve())
            expected = row['sha256']
            require(path not in self.expected or self.expected[path] == expected,
                    'Conflicting file pins: '+path)
            if path not in self.hashes:
                # First encounter in this pass reads fresh bytes; only later repeats reuse it.
                self.hashes[path] = sha(path, fresh=True)
                self.bytes_hashed += Path(path).stat().st_size
            require(self.hashes[path] == expected, 'Stale file pin: '+path)
            # Only a matching pin binds this pass; a caught stale row must not poison later rows.
            self.expected[path] = expected
