"""Compact read-only lookup tables for large word statistics (low RAM).

A str -> int table is kept as two NumPy arrays: sorted 64-bit hashes of the keys and their values. Arrays are cached on
disk as .npy files and memory-mapped, so a process only pays for the pages it touches instead of building millions of
Python objects. Lookups hash the key (BLAKE2b, 8 bytes) and binary-search; a 64-bit hash collision is astronomically
unlikely for these vocabularies (~10^6 keys), and every caller re-checks candidates by spelling anyway.
"""
from hashlib import blake2b
import json
import os
from pathlib import Path

import numpy as np


def h64(text):
    return int.from_bytes(blake2b(text.encode('utf-8'), digest_size=8).digest(), 'little')


class Counts:
    """dict-like str -> int (get, in, len) over sorted hash/value arrays."""

    def __init__(self, keys, values=None):
        self.keys, self.values = keys, values

    @classmethod
    def build(cls, mapping):
        keys = np.fromiter((h64(k) for k in mapping), dtype=np.uint64, count=len(mapping))
        values = np.fromiter((min(int(v), 2 ** 31 - 1) for v in mapping.values()), dtype=np.int32, count=len(mapping)) \
            if isinstance(mapping, dict) else None
        order = np.argsort(keys, kind='stable')
        return cls(keys[order], values[order] if values is not None else None)

    def _find(self, key):
        h = np.uint64(h64(key))
        i = int(np.searchsorted(self.keys, h))
        return i if i < len(self.keys) and self.keys[i] == h else -1

    def get(self, key, default=0):
        i = self._find(key)
        if i < 0:
            return default
        return int(self.values[i]) if self.values is not None else True

    def __contains__(self, key):
        return self._find(key) >= 0

    def __len__(self):
        return len(self.keys)

    def save(self, folder, name):
        folder.mkdir(parents=True, exist_ok=True)
        np.save(folder / f'{name}.keys.npy', self.keys)
        if self.values is not None:
            np.save(folder / f'{name}.values.npy', self.values)

    @classmethod
    def load(cls, folder, name):
        keys = np.load(folder / f'{name}.keys.npy', mmap_mode='r')
        path = folder / f'{name}.values.npy'
        return cls(keys, np.load(path, mmap_mode='r') if path.exists() else None)


class Groups:
    """str -> list of words (e.g. a SymSpell deletion -> the words it came from), as sorted hashes + word ids."""

    def __init__(self, keys, ids, words):
        self.keys, self.ids, self.words = keys, ids, words

    @classmethod
    def build(cls, pairs, words):
        """pairs: iterable of (key, word id)."""
        hashes, ids = [], []
        for key, wid in pairs:
            hashes.append(h64(key))
            ids.append(wid)
        keys = np.array(hashes, dtype=np.uint64)
        idarr = np.array(ids, dtype=np.int32)
        order = np.argsort(keys, kind='stable')
        return cls(keys[order], idarr[order], words)

    def get(self, key, default=()):
        h = np.uint64(h64(key))
        lo = int(np.searchsorted(self.keys, h, 'left'))
        hi = int(np.searchsorted(self.keys, h, 'right'))
        return [self.words[i] for i in self.ids[lo:hi]] if hi > lo else default

    def save(self, folder, name):
        folder.mkdir(parents=True, exist_ok=True)
        np.save(folder / f'{name}.keys.npy', self.keys)
        np.save(folder / f'{name}.ids.npy', self.ids)
        (folder / f'{name}.words.txt').write_text('\n'.join(self.words), encoding='utf-8')

    @classmethod
    def load(cls, folder, name):
        words = (folder / f'{name}.words.txt').read_text(encoding='utf-8').split('\n')
        return cls(np.load(folder / f'{name}.keys.npy', mmap_mode='r'), np.load(folder / f'{name}.ids.npy', mmap_mode='r'), words)


def signature(*parts):
    """A short id for the inputs a cache was built from (file names and sizes, code constants)."""
    digest = blake2b(digest_size=8)
    for part in parts:
        if isinstance(part, Path):
            try:
                st = part.stat()
                part = f'{part.name}:{st.st_size}'
            except OSError:
                part = f'{part.name}:missing'
        digest.update(json.dumps(part, sort_keys=True, default=sorted).encode('utf-8'))
    return digest.hexdigest()


def writable(folder):
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / '.write-test'
        probe.write_text('', encoding='utf-8')
        os.remove(probe)
        return True
    except OSError:
        return False
