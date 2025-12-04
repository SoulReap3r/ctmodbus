"""
Tag and TagGroup system for ctmodbus.
Implements simple SCADA-style named register groups.

Example:
    tags.add("input1", "input_register", "1")
    tags.add("config2", "holding_register", "50-69")
    tags.group("configs", ["config1", "config2"])
"""

import json
from ctmodbus.common import Loops


class Tag:
    def __init__(self, name: str, tag_type: str, csr: str):
        self.name = name
        self.type = tag_type  # input_register, holding_register, discrete_input, coils
        self.csr = csr
        self.range = Loops(csr, minimum=0, maximum=65535)

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "csr": self.csr,
        }

    @staticmethod
    def from_dict(d):
        return Tag(d["name"], d["type"], d["csr"])


class TagGroup:
    def __init__(self, name: str, tag_names: list):
        self.name = name
        self.tag_names = tag_names  # names only! resolved at runtime

    def to_dict(self):
        return {
            "name": self.name,
            "tags": self.tag_names,
        }

    @staticmethod
    def from_dict(d):
        return TagGroup(d["name"], d["tags"])


class TagManager:
    def __init__(self):
        self.tags = {}        # name → Tag
        self.groups = {}      # name → TagGroup

    # ----------------------------------------------------------
    # TAGS
    # ----------------------------------------------------------

    def add_tag(self, name: str, tag_type: str, csr: str):
        if name in self.tags:
            raise ValueError(f"Tag '{name}' already exists.")
        tag = Tag(name, tag_type, csr)
        self.tags[name] = tag
        return tag

    def get_tag(self, name: str):
        if name not in self.tags:
            raise KeyError(f"Tag '{name}' does not exist.")
        return self.tags[name]

    # ----------------------------------------------------------
    # GROUPS
    # ----------------------------------------------------------

    def add_group(self, name: str, tag_names: list):
        for t in tag_names:
            if t not in self.tags:
                raise ValueError(f"Tag '{t}' not found for group {name}.")
        self.groups[name] = TagGroup(name, tag_names)
        return self.groups[name]

    def get_group(self, name):
        if name not in self.groups:
            raise KeyError(f"Group '{name}' does not exist.")
        return self.groups[name]

    # ----------------------------------------------------------
    # EXPORT / IMPORT
    # ----------------------------------------------------------

    def export_to_file(self, filename):
        data = {
            "tags": [t.to_dict() for t in self.tags.values()],
            "groups": [g.to_dict() for g in self.groups.values()],
        }
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        return filename

    def import_from_file(self, filename):
        with open(filename, "r") as f:
            data = json.load(f)

        self.tags = {d["name"]: Tag.from_dict(d) for d in data.get("tags", [])}
        self.groups = {d["name"]: TagGroup.from_dict(d) for d in data.get("groups", [])}
