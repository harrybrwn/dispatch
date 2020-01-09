import os

class Env:
    def __init__(self, name):
        self.name = name

    def __get__(self, inst, owner):
        return os.getenv(self.name)

    def __set__(self, inst, value):
        self.name = value

    def __str__(self):
        return os.getenv(self.name)

    def __repr__(self):
        return f'${self.name}'

# TODO: when used as an annotaion, should accept json input
# and convert to dict
Json = None
