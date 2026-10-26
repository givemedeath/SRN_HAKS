"""Opt-in, machine-local SHA-256 cache for the shared-tool launcher's input pins.

A headkit stage launch declares ~3,800 inputs (~1.4 GB) and the launcher hashed every one before and after the run:
about 12-15 s per launch (41% of all launch time in the troll head batch v2). With `SRN_LAUNCH_HASH_CACHE` set to a
SQLite file, a file whose identity and modification stamp are unchanged since it was last hashed reuses that digest.

What a hit trusts: path, size, st_mtime_ns, st_ino (the NTFS file index) and st_dev all equal to the row recorded when
the bytes were hashed. A writer that keeps size and timestamp unchanged (for example one that resets mtime) is not
detected; without the variable every file is hashed in full, as before. Guards:
- a file modified within `RECENT_SECONDS` of the stat is hashed and never stored, because its timestamp may not yet
  reflect a write still in progress (the racy-timestamp case);
- a digest is stored only when the stat before and after hashing match;
- rows are keyed by the resolved path; any stat difference is a miss and the row is replaced.
The cache file is local machine state (never a portable lock or a receipt input). Several launches may share it
(SQLite WAL, short transactions, retry on lock).
"""
import os
from pathlib import Path
import sqlite3
import time

from shared_toolchain import sha

RECENT_SECONDS = 2.0
ENVIRONMENT = 'SRN_LAUNCH_HASH_CACHE'


def stamp(stat):
    # Text: Windows file indexes and volume serials can exceed SQLite's signed 64-bit integers.
    return f'{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ino}:{stat.st_dev}'


class HashCache:
    """sha(path) with a stat-keyed digest cache; counts hits, misses and recent-file refusals for the receipt."""

    def __init__(self, path, *, recent=RECENT_SECONDS, clock=time.time):
        self.path = Path(path).resolve(); self.recent = recent; self.clock = clock
        self.hits = self.misses = self.recentRefusals = 0; self.pending = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        for attempt in range(100):  # first-time setup by concurrent launches: switching to WAL needs an exclusive lock
            try:
                self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=NORMAL')
                self.db.execute('CREATE TABLE IF NOT EXISTS digests (path TEXT PRIMARY KEY, stamp TEXT, sha256 TEXT)'); break
            except sqlite3.OperationalError as error:
                if 'locked' not in str(error) or attempt == 99:raise
                time.sleep(.05)

    def sha(self, path):
        key = str(Path(path).resolve()); before = os.stat(key); current = stamp(before)
        row = self.db.execute('SELECT stamp, sha256 FROM digests WHERE path=?', (key,)).fetchone()
        if row is not None and row[0] == current:
            self.hits += 1; return row[1]
        self.misses += 1; digest = sha(key)
        if self.clock() - before.st_mtime_ns / 1e9 < self.recent:
            self.recentRefusals += 1; return digest
        if stamp(os.stat(key)) == current:
            self.pending.append((key, current, digest))
        return digest

    def flush(self):
        """Store this pass's new digests in one transaction (thousands of single-row commits are slow)."""
        if self.pending:
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                self.db.executemany('INSERT OR REPLACE INTO digests VALUES (?, ?, ?)', self.pending)
            self.pending = []

    def store(self, path, digest):
        """The read-only content-addressed copy of `path` (bytes `digest`) beside the cache, created once and verified
        (stat-keyed) on every use. Concurrent creators write a private temporary file and rename it into place."""
        target = self.path.parent / 'helper-store' / digest[:2] / (digest + Path(path).suffix)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f'{target.name}.{os.getpid()}.tmp'); temporary.write_bytes(Path(path).read_bytes())
            if sha(temporary) != digest:temporary.unlink();raise ValueError('Helper changed while storing: ' + str(path))
            os.chmod(temporary, 0o444)
            try:os.replace(temporary, target)
            except OSError:  # lost a publication race (Windows refuses to replace the read-only winner): drop ours
                os.chmod(temporary, 0o644); temporary.unlink(missing_ok=True)
            if not target.exists():raise ValueError('Helper store entry missing: ' + str(target))
        if self.sha(target) != digest:raise ValueError('Helper store entry changed: ' + str(target))
        return target

    def report(self):
        return {'path': str(self.path), 'hits': self.hits, 'misses': self.misses, 'recentRefusals': self.recentRefusals,
                'recentSeconds': self.recent, 'trusts': 'size, mtime_ns, file index and device unchanged since hashed'}

    def close(self):
        self.flush(); self.db.close()


def from_environment():
    """The cache named by SRN_LAUNCH_HASH_CACHE, or None (full hashing)."""
    value = os.environ.get(ENVIRONMENT)
    return HashCache(value) if value else None
