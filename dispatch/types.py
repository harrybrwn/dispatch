import os

class Env:
    def __init__(self, name):
        if name.startswith('$'):
            name = name[1:]
        self.name = name

    def __get__(self, inst, owner):
        return self._get()

    def __set__(self, inst, value):
        self.name = value

    def __str__(self) -> str:
        return self._get()

    def __repr__(self) -> str:
        return f"'${self.name}'"

    def __bool__(self) -> bool:
        return bool(self._get())

    def _get(self) -> str:
        return os.getenv(str(self.name)) or self.name

# TODO: when used as an annotaion, should accept json input
# and convert to dict
Json = None
