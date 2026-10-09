"""Bounded in-memory thumbnails; keys include source file metadata and edit settings."""
from collections import OrderedDict
from threading import Lock


class PreviewCache:
    def __init__(self, capacity=96):
        self.capacity = capacity
        self.entries = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            if key not in self.entries:
                return None
            self.entries.move_to_end(key)
            return self.entries[key].copy()

    def put(self, key, image):
        with self.lock:
            self.entries[key] = image.copy()
            self.entries.move_to_end(key)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)

    def clear(self):
        with self.lock:
            self.entries.clear()
