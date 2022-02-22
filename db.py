import json
import os.path
from typing import List


class DB:
    used_ids: List[str] = []

    def __init__(self, path: str = "db.json"):
        self.path = path

        if not os.path.exists(path):
            self.save()
        self.load()

    def raw(self):
        return dict(
            used_ids=self.used_ids
        )

    def load(self):
        file = json.load(open(self.path, 'r'))

        self.used_ids = file['used_ids'] if file.get('used_ids') else []

    def save(self):
        json.dump(self.raw(), open(self.path, 'w'), indent=4)
