"""A block of the resource file before layout."""


class Block:
    def __init__(self, bid, type_, data, name, flags=0):
        self.id, self.type, self.data, self.name, self.flags = bid, type_, bytes(data), name, flags
